from flask import current_app
import json
import os
from urllib.request import urlopen
from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, Alignment
from openpyxl.styles.fills import PatternFill, Color
from openpyxl.styles.borders import Border, Side
from datetime import datetime, time

from ....tz import ph_now
from ....workbook_download import in_memory
from .trades_done_average import TradesDoneAverage
from ..models import get_short_average

HEADER_HEIGHT = 18.75
DETAIL_HEIGHT = 45
DIVIDER_HEIGHT = 18.75
DIVIDER_COLOR = "00000000"
RATE_COLOR = "00FFFF99"

# Short-book types that exist only in tbl_transaction_short. Borrow/Return Shares are
# double-booked into the long book and already print from there.
SHORT_BOOK_TYPES = ("Sell (Short)", "Buy (Pay Short)")

CODE_TO_SHRINK = ('0857', '0981', '0939', '1099', '1288', '2196', '3993')

HKD_FORMAT = "[$HKD]* #,##0.00; ([$HKD]* #,##0.00)"
PERCENT_FORMAT = "0.00%;( 0.00% )"

# Free daily rates, no key; reachable from PythonAnywhere. HKD per one unit of the currency.
FX_URL = "https://open.er-api.com/v6/latest/{ccy}"
FX_TIMEOUT = 5

thin_border = Border(left=Side(style='thin'),
                     right=Side(style='thin'),
                     top=Side(style='thin'),
                     bottom=Side(style='thin'))

# double_rule_border = Border(bottom=Side(style='double'))


def fetch_hkd_rate(ccy):
    """Today's HKD for one unit of ccy and the feed's update time, or None when
    the feed cannot be read -- the rate is then left for the user to enter."""
    try:
        with urlopen(FX_URL.format(ccy=ccy), timeout=FX_TIMEOUT) as response:
            data = json.load(response)
        rate = float(data["rates"]["HKD"])
        if data.get("result") != "success" or rate <= 0:
            raise ValueError(f"unusable reply: result={data.get('result')!r}, HKD={rate}")
        return round(rate, 4), data.get("time_last_update_utc", "")
    except Exception as e:
        current_app.logger.warning("No %s/HKD rate from %s: %s", ccy, FX_URL.format(ccy=ccy), e)
        return None


class DownloadTradesDoneWithGainLoss:
    def __init__(self, db, trade_date, trade_summary):
        self.db = db
        self.trade_date = trade_date
        self.trade_summary = trade_summary

        self.template_file = os.path.join(
            current_app.instance_path,
            "excel_templates",
            "trades_done_with_gain_loss.xlsx"
        )

        self.download_name = f"{trade_date} Trades Done with gain loss.xlsx"

        self.create_file()

    def create_file(self):
        wb = load_workbook(self.template_file)
        ws = wb["Sheet"]
        ws.title = f"{int(self.trade_date[-2:])}"

        ws["A2"].value = "Date: " + datetime.strptime(self.trade_date, "%Y-%m-%d").strftime("%B %d, %Y")
        ws["E2"].value = self.time_made()

        row_num = 5
        if self.trade_summary.accus:
            row_num = self.write_term_sheet(ws, row_num, self.trade_summary.accus, "ACCU")
            row_num += 2

        if self.trade_summary.decus:
            row_num = self.write_term_sheet(ws, row_num, self.trade_summary.decus, "DECU")
            row_num += 2

        short_transactions = {
            ccy: {t: by_bank for t, by_bank in types.items() if t in SHORT_BOOK_TYPES}
            for ccy, types in self.trade_summary.short_transactions.items()
        }
        short_transactions = {ccy: types for ccy, types in short_transactions.items() if types}
        if self.trade_summary.transactions or short_transactions:
            row_num = self.write_currencies(ws, row_num, self.trade_summary.transactions, short_transactions)

        if self.trade_summary.transfers:
            row_num = self.write_transfers(ws, row_num, self.trade_summary.transfers)
            row_num += 2

        ws.print_area = f"A1:N{row_num}"
        self.output = in_memory(wb)
        wb.close()

    def time_made(self):
        # A fixed time in place of the template's =NOW(), which changes whenever the
        # file is opened: the minute it is made on the trade date, the 4:00 PM close
        # for a later one, as Alvin types them (2026-10-27). E2 keeps h:mm AM/PM.
        now = ph_now()
        if now.date().isoformat() == self.trade_date:
            return time(now.hour, now.minute)
        return time(16, 0)

    def write_term_sheet(self, ws, row_num, term_sheets, _type):
        # Header
        cols = {
            "A": "Accu" if _type == "ACCU" else "Decu",
            "B": "",
            "C": "Stock",
            "D": "Shares",
            "E": "Spot",
            "F": "Strike Rate",
            "G": "Strike",
            "H": "KO",
            "I": "KO Rate",
            "J": "Tenor",
            "K": "GTD"
        }
        for col, label in cols.items():
            cell = ws[f"{col}{row_num}"]
            cell.value = label

            if col == "A":
                cell.font = Font(size=14, bold=True)
                cell.alignment = Alignment(horizontal="center")
                if _type == "ACCU":
                    cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor=Color("0099CC00"))
                else:
                    cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor=Color("00FF8080"))
            else:
                cell.font = Font(size=11, bold=True)
                cell.alignment = Alignment(horizontal="center")
                cell.border = thin_border
        ws.row_dimensions[row_num].height = HEADER_HEIGHT
        row_num += 1

        # Details
        for ccy in term_sheets:
            for ts in term_sheets[ccy]:
                cols = {
                    "A": ts.bank_name,
                    "B": ts.code,
                    "C": ts.stock_name,
                    "D": ts.shares,
                    "E": ts.spot,
                    "F": ts.strike_rate,
                    "G": f'=TEXT(E{row_num}*F{row_num}/100,"0.0000")&CHAR(10)&"("&TEXT(F{row_num},"0.00")&"%)"',
                    "H": f'=TEXT(E{row_num}*I{row_num}/100,"0.0000")&CHAR(10)&"("&TEXT(I{row_num},"0.00")&"%)"',
                    "I": ts.ko_rate,
                    "J": ts.tenor,
                    "K": ts.gtd
                }

                for col, label in cols.items():
                    cell = ws[f"{col}{row_num}"]
                    cell.value = label

                    if ts.code in CODE_TO_SHRINK:
                        font_size = 9
                    else:
                        font_size = 11

                    if col == "A":
                        cell.font = Font(size=11, bold=True)
                    elif col == "C":
                        cell.font = Font(size=font_size)
                    else:
                        cell.font = Font(size=11)

                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrapText=True)

                ws.row_dimensions[row_num].height = DETAIL_HEIGHT
                row_num += 1

        return row_num

    def write_currencies(self, ws, row_num, transactions, short_transactions):
        """Long-book then short-book sections, one currency at a time, HKD first.

        When a currency other than HKD has a gain/loss section, its cost and
        gain/loss are converted to HKD at a rate kept in its own cell (filled
        from today's feed, typed over by the user), under an HKD sub total, and
        all of them are added up in HKD at the end. HKD-only days are unchanged."""
        currencies = self.currency_order(set(transactions) | set(short_transactions))
        foreign = [ccy for ccy in currencies
                   if ccy != "HKD" and self.has_gain(ccy, transactions, short_transactions)]

        totals = []
        self.last_row = row_num
        for ccy in currencies:
            first_row = row_num
            if ccy in transactions:
                row_num = self.write_transactions(ws, row_num, {ccy: transactions[ccy]})
                row_num += 2
            if ccy in short_transactions:
                row_num = self.write_transactions(ws, row_num, {ccy: short_transactions[ccy]}, short_book=True)
                row_num += 2

            if not foreign or not self.has_gain(ccy, transactions, short_transactions):
                continue

            # SUBTOTAL(9,...) skips the bank and TOTAL rows inside the range, so
            # these add up the currency's detail rows only.
            last_row = self.last_row
            cost = f"SUBTOTAL(9,L{first_row}:L{last_row})"
            gain = f"SUBTOTAL(9,M{first_row}:M{last_row})"
            if ccy == "HKD":
                total_row = last_row + 2
                self.write_label(ws, f"K{total_row}", "HKD Sub Total")
                self.write_hkd_total(ws, total_row, f"={cost}", f"={gain}")
            else:
                total_row = last_row + 1
                self.write_label(ws, f"J{total_row}", f"{ccy} → HKD")
                self.write_rate(ws, f"K{total_row}", ccy)
                self.write_hkd_total(ws, total_row, f"={cost}*$K${total_row}", f"={gain}*$K${total_row}")
            totals.append((ccy, total_row))
            self.last_row = total_row
            row_num = total_row + 2

        if len(totals) > 1:
            grand_row = self.last_row + 2
            names = [ccy for ccy, _ in totals]
            label = ", ".join(names[:-1]) + " and " + names[-1]
            self.write_label(ws, f"K{grand_row}", f"{label} Grand Total")
            self.write_hkd_total(ws, grand_row,
                                 "=" + "+".join(f"L{r}" for _, r in totals),
                                 "=" + "+".join(f"M{r}" for _, r in totals))
            self.last_row = grand_row
            row_num = grand_row + 3

        return row_num

    def currency_order(self, currencies):
        priority = [row["ccy_id"] for row in self.db.execute("SELECT ccy_id FROM tbl_currency ORDER BY priority")]
        return sorted(currencies, key=lambda ccy: (ccy != "HKD", priority.index(ccy) if ccy in priority else len(priority)))

    @staticmethod
    def has_gain(ccy, transactions, short_transactions):
        # The sections write_transactions gives Cost and Gain / Loss columns.
        return "Sell (Spot)" in transactions.get(ccy, {}) or "Buy (Pay Short)" in short_transactions.get(ccy, {})

    @staticmethod
    def write_label(ws, coordinate, label):
        cell = ws[coordinate]
        cell.value = label
        cell.font = Font(size=11, bold=True)
        cell.alignment = Alignment(horizontal="right", vertical="center")

    @staticmethod
    def write_rate(ws, coordinate, ccy):
        # A blank rate would read as 0 and leave a plausible HKD total without the
        # currency in it; the text makes every total that uses it show #VALUE!.
        result = fetch_hkd_rate(ccy)
        cell = ws[coordinate]
        if result:
            rate, updated = result
            cell.value = rate
            cell.comment = Comment(f"HKD per 1 {ccy}, open.er-api.com, updated {updated}. "
                                   f"Type over it to change the rate.", "LTV")
        else:
            cell.value = "enter rate"
            cell.comment = Comment(f"No rate could be read from open.er-api.com. "
                                   f"Type the HKD per 1 {ccy} rate here.", "LTV")
        cell.number_format = "0.0000"
        cell.font = Font(size=11, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
        cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor=Color(RATE_COLOR))

    @staticmethod
    def write_hkd_total(ws, row_num, cost, gain):
        for col, value in (("L", cost), ("M", gain), ("N", f"=M{row_num}/L{row_num}")):
            cell = ws[f"{col}{row_num}"]
            cell.value = value
            cell.border = thin_border
            cell.font = Font(size=11, bold=True)
            if col == "N":
                cell.number_format = PERCENT_FORMAT
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.number_format = HKD_FORMAT
                cell.alignment = Alignment(horizontal="right", vertical="center")
        ws.row_dimensions[row_num].height = DIVIDER_HEIGHT

    def write_transactions(self, ws, row_num, transactions, short_book=False):
        """Long-book blocks, or with short_book the short-book blocks: a short sale shows
        the new short average, as a buy shows its new long average, and a cover's gain is
        the covered shares at the short average less what the cover cost."""
        for ccy in transactions:
            for transaction_type in transactions[ccy]:
                if "Transfer" in transaction_type:
                    continue

                if short_book:
                    show_average = transaction_type == "Sell (Short)"
                    show_gain = transaction_type == "Buy (Pay Short)"
                else:
                    show_average = "Buy" in transaction_type
                    show_gain = transaction_type == "Sell (Spot)"

                start_row = row_num
                trade_total = False
                # Headers
                cols = {
                    "A": "BUY" if ("Buy" in transaction_type or transaction_type == "Borrow Shares") else "SELL",
                    "D": ccy,
                    "E": "Price",
                    "G": "Shares",
                    "H": "Total"
                }

                if show_average:
                    cols["J"] = "Average"
                elif show_gain:
                    cols["L"] = f"Short Sale {ccy}" if short_book else f"Cost {ccy}"
                    cols["M"] = f"Lost {ccy}"
                    cols["N"] = "% Lost"

                for col, label in cols.items():
                    cell = ws[f"{col}{row_num}"]
                    cell.value = label

                    if col in ("A", "D"):
                        cell.font = Font(size=14, bold=True)
                        cell.alignment = Alignment(horizontal="center")
                    else:
                        cell.font = Font(size=11, bold=True)
                        cell.alignment = Alignment(horizontal="center")
                        cell.border = thin_border

                ws.merge_cells(f"J{row_num}:K{row_num}")

                ws.row_dimensions[row_num].height = HEADER_HEIGHT
                row_num += 1

                # Details
                bank_name_count = len(transactions[ccy][transaction_type])
                line_count = sum(len(trades) for stocks in transactions[ccy][transaction_type].values()
                                 for trades in stocks.values())
                for i, bank_name in enumerate(transactions[ccy][transaction_type]):
                    account_start_row = row_num
                    for stock_name in transactions[ccy][transaction_type][bank_name]:
                        trade_count = len(transactions[ccy][transaction_type][bank_name][stock_name])
                        if trade_count > 1:
                            trade_total = True
                        for i_trade, trade in enumerate(transactions[ccy][transaction_type][bank_name][stock_name]):
                            quantity = float(trade["quantity"].replace(",", ""))
                            price = float(trade["price"].replace(",", ""))
                            float_check = str(price)
                            loc = float_check.find(".")
                            length = len(float_check) - loc - 1
                            price_decimal = len(float_check[-length:])

                            code = trade["code"]
                            bank_id = trade["bank_id"]

                            cols = {
                                "A": bank_name,
                                "B": f'=A{row_num}&D{row_num}&MID(C{row_num},FIND("(",C{row_num})+1,4)',
                                "C": stock_name,
                                "D": transaction_type,
                                "E": price,
                                "G": quantity,
                                "H": f'=E{row_num}*G{row_num}'
                            }

                            if show_average:
                                if i_trade + 1 == trade_count:
                                    average = self.average(trade, short_book)
                                else:
                                    average = None

                                cols["J"] = average
                            elif show_gain:
                                average = self.average(trade, short_book, cover=True)
                                cols["L"] = f'=G{row_num}*O{row_num}'
                                cols["M"] = f'=L{row_num}-H{row_num}' if short_book else f'=H{row_num}-L{row_num}'
                                cols["N"] = f'=M{row_num}/L{row_num}'
                                cols["O"] = average

                            for col, value in cols.items():
                                cell = ws[f"{col}{row_num}"]
                                cell.value = value

                                cell.alignment = Alignment(horizontal="center", vertical="center", wrapText=True)
                                cell.border = thin_border

                                if col == "A":
                                    cell.font = Font(size=11, bold=True)
                                else:
                                    cell.font = Font(size=9) if col == "C" and code in CODE_TO_SHRINK else Font(size=11)

                                if col == "E":
                                    if price_decimal < 3:
                                        cell.number_format = "#,##0.00"
                                    else:
                                        cell.number_format = "#,##0.0000"
                                elif col == "G":
                                    cell.number_format = "#,##0"
                                elif col == "H":
                                    cell.number_format = f"[${ccy}] #,##0.00"
                                elif col == "J":
                                    cell.number_format = "#,##0.0000"
                                elif col in ("L", "M"):
                                    if show_gain:
                                        cell.number_format = f"[${ccy}]* #,##0.00; ([${ccy}]* #,##0.00)"
                                        cell.alignment = Alignment(horizontal="right", vertical="center")
                                elif col in ("N", ):
                                    if show_gain:
                                        cell.number_format = "0.00%;( 0.00% )"

                            if "Buy" in transaction_type:
                                average = None
                                cols["J"] = average

                            ws.merge_cells(f"J{row_num}:K{row_num}")

                            ws.row_dimensions[row_num].height = DETAIL_HEIGHT

                            row_num += 1

                    if i != bank_name_count:
                        # Bank divider
                        cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
                        if show_average:
                            cols += ["J", "K"]

                        for col in cols:
                            cell = ws[f"{col}{row_num}"]
                            cell.fill = PatternFill(patternType="solid", fill_type="solid", fgColor=DIVIDER_COLOR)

                        # Cost totals -- none in a section of one trade line, where they
                        # would only repeat it; the divider stays (Alvin, 2026-10-27)
                        if show_gain:
                            cols = {"J": f'=SUM(H{account_start_row}:H{row_num - 1})'}
                            if line_count > 1:
                                cols.update({
                                    "L": f"=SUBTOTAL(9,L{account_start_row}:L{row_num - 1})",
                                    "M": f"=SUBTOTAL(9,M{account_start_row}:M{row_num - 1})",
                                    "N": f"=M{row_num}/L{row_num}",
                                })

                            for col, value in cols.items():
                                if col == "J":
                                    cell = ws[f"{col}{row_num-1}"]
                                    if account_start_row != row_num-1:
                                        cell.value = value
                                    cell.font = Font(size=11)
                                else:
                                    cell = ws[f"{col}{row_num}"]
                                    cell.value = value
                                    cell.border = thin_border
                                    cell.font = Font(size=11, bold=True)

                                if col in ("J", "L", "M"):
                                    cell.number_format = f"[${ccy}]* #,##0.00; ([${ccy}]* #,##0.00)"
                                    cell.alignment = Alignment(horizontal="right", vertical="center")
                                elif col in ("N",):
                                    cell.number_format = "0.00%;( 0.00% )"
                                    cell.alignment = Alignment(horizontal="center", vertical="center")

                        ws.row_dimensions[row_num].height = DIVIDER_HEIGHT
                        row_num += 1

                # Fix the Gain/Loss Ccy Header
                if show_gain:
                    cell = ws[f"M{start_row}"]
                    cell.value = f'=IF(COUNTIF(M{start_row+1}:M{row_num-1},">=0")<>0,' \
                                 f'IF(COUNTIF(M{start_row+1}:M{row_num-1},"<0")<>0,"Gain / Loss", "Gain"),' \
                                 f'"Loss")&" {ccy}"'

                    cell = ws[f"N{start_row}"]
                    cell.value = f'="% "&IF(COUNTIF(N{start_row+1}:N{row_num-1},">=0")<>0,' \
                                 f'IF(COUNTIF(N{start_row+1}:N{row_num-1},"<0")<>0,"Gain / Loss", "Gain"),' \
                                 f'"Loss")'

                # Footes
                if bank_name_count > 1 or trade_total:
                    end_row = row_num - 1
                    cols = {
                        "E": "TOTAL",
                        "G": f"=SUM(G{start_row}:G{end_row})",
                        "H": f"=SUM(H{start_row}:H{end_row})"
                    }

                    # With one bank the subtotal row just above already shows Cost / Gain / %,
                    # so the footer only repeats them (Alvin clears them by hand, 2026-10-27).
                    if show_gain and bank_name_count > 1:
                        # SUBTOTAL(9,...) ignores any nested SUBTOTAL cells inside its range,
                        # so this picks up the detail rows only and never double-counts the
                        # per-bank subtotal rows written above.
                        cols["L"] = f"=SUBTOTAL(9,L{start_row}:L{end_row})"
                        cols["M"] = f"=SUBTOTAL(9,M{start_row}:M{end_row})"
                        cols["N"] = f"=M{row_num}/L{row_num}"

                    for col, value in cols.items():
                        cell = ws[f"{col}{row_num}"]
                        cell.value = value
                        cell.border = thin_border
                        cell.alignment = Alignment(horizontal="center")
                        cell.font = Font(size=11)

                        if col == "G":
                            cell.number_format = "#,##0"
                        elif col == "H":
                            cell.number_format = f"[${ccy}] #,##0.00"
                        elif col in ("L", "M"):
                            cell.number_format = f"[${ccy}]* #,##0.00; ([${ccy}]* #,##0.00)"
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            cell.font = Font(size=11, bold=True)
                        elif col == "N":
                            cell.number_format = "0.00%;( 0.00% )"
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                            cell.font = Font(size=11, bold=True)

                # The last row written: the TOTAL footer, else the last bank divider
                self.last_row = row_num if (bank_name_count > 1 or trade_total) else row_num - 1
                row_num += 2

        return row_num

    def average(self, trade, short_book, cover=False):
        if short_book:
            # A cover is measured against the short it closes -- the average carried
            # just before it -- not the day's closing average after a later short sale.
            return get_short_average(self.db, trade["bank_ref"], trade["code_ref"], self.trade_date,
                                     before_ref=trade["ref_num"] if cover else None)
        return TradesDoneAverage(db=self.db, trade_date=self.trade_date,
                                 code=trade["code"], bank_id=trade["bank_id"]).average

    def write_transfers(self, ws, row_num, transfers):
        # Section header
        cell = ws[f"A{row_num}"]
        cell.value = "Transfer of Stocks"
        cell.font = Font(size=14, bold=True)
        # Left: column A is narrow, so a centred 14 pt heading spills both ways
        cell.alignment = Alignment(horizontal="left")

        cell = ws[f"J{row_num}"]
        cell.value = "Average"
        cell.font = Font(size=11, bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
        ws.merge_cells(f"J{row_num}:K{row_num}")

        ws.row_dimensions[row_num].height = HEADER_HEIGHT
        row_num += 1

        for i, t in enumerate(transfers):
            # Stock name line
            cell = ws[f"A{row_num}"]
            cell.value = f"{t['seq']}) {t['stock_name']} ({t['code']})"
            cell.font = Font(size=11, bold=True)
            ws.row_dimensions[row_num].height = HEADER_HEIGHT
            row_num += 1

            # From / to detail line — average of the receiving account after the transfer
            average = TradesDoneAverage(
                db=self.db, trade_date=self.trade_date,
                code=t['code'], bank_id=t['counter_bank_id'],
                include_transfers=True,
            ).average

            cell = ws[f"A{row_num}"]
            cell.value = f"from {t['bank_name']} to {t['counter_bank_name']}"
            cell.font = Font(size=11)

            cell = ws[f"H{row_num}"]
            cell.value = f"{t['quantity']:,.0f} shares"
            cell.font = Font(size=11)
            cell.alignment = Alignment(horizontal="center")

            cell = ws[f"J{row_num}"]
            cell.value = average if average else None
            cell.font = Font(size=11)
            cell.alignment = Alignment(horizontal="center")
            cell.number_format = "#,##0.0000"
            ws.merge_cells(f"J{row_num}:K{row_num}")

            ws.row_dimensions[row_num].height = HEADER_HEIGHT
            row_num += 1

            # Blank separator between items
            if i < len(transfers) - 1:
                row_num += 1

        return row_num
