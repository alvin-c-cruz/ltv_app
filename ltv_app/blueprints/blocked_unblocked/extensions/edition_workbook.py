"""<date> Blocked Unblocked.xlsx. Plan A writes its data sheet, Equities: one row per account and position, every
figure the printed sheets draw on (spec section 7). The printed sheets are added by plans B to D."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from ....tz import ph_today
from ....workbook_download import in_memory

SHARES = "#,##0;[Red](#,##0)"
MONEY = "#,##0.00;[Red](#,##0.00)"
PRICE = "#,##0.0000"
PERCENT = "0.00%;[Red](0.00%)"

# (header, EditionRow attribute, number format, column width)
COLUMNS = (
    ("Account", "bank_id", None, 9),
    ("Account name", "bank_name", None, 28),
    ("Code", "code", "@", 8),
    ("Stock", "stock_name", None, 26),
    ("Side", "side", None, 7),
    ("Key", "key", None, 13),
    ("Ccy", "ccy", None, 6),
    ("Shares", "shares", SHARES, 12),
    ("Average", "average", PRICE, 12),
    ("Cost", "cost", MONEY, 16),
    ("To block", "to_block", SHARES, 12),
    ("Blocked", "blocked", SHARES, 12),
    ("Unblocked", "unblocked", SHARES, 12),
    ("Short", "short", SHARES, 12),
    ("Close", "close", PRICE, 11),
    ("Close from", "close_from", None, 24),
    ("Market value", "market", MONEY, 16),
    ("Gain / Loss", "gain", MONEY, 16),
    ("Gain / Loss %", "gain_pct", PERCENT, 12),
)
HEADER_ROW = 5


class EditionWorkbook:
    def __init__(self, edition, notices=()):
        self.download_name = f"{edition.as_of} Blocked Unblocked.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Equities"
        ws["A1"] = "Blocked Unblocked: Equities"
        ws["A1"].font = Font(size=14, bold=True)
        ws["A2"] = f"As of {edition.as_of}; holdings include that day's fixings"
        if edition.as_of < ph_today().strftime("%Y-%m-%d"):
            ws["A2"] = (f"As of {edition.as_of}; holdings include that day's fixings. Contracts knocked out or made "
                        f"inactive since {edition.as_of} are not counted in To block.")
        ws["A3"] = f"Prices: {edition.price_label}"
        lines = list(notices)
        if edition.unpriced:
            lines.append("No price for: " + ", ".join(edition.unpriced))
        if not edition.rows:
            lines.append(f"No positions on {edition.as_of}")
        if lines:
            ws["A4"] = "  |  ".join(lines)
            ws["A4"].font = Font(bold=True, color="C00000")
        for i, (header, _, _, width) in enumerate(COLUMNS, start=1):
            cell = ws.cell(HEADER_ROW, i, header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            ws.column_dimensions[cell.column_letter].width = width
        for r, row in enumerate(edition.rows, start=HEADER_ROW + 1):
            for i, (_, attribute, number_format, _) in enumerate(COLUMNS, start=1):
                cell = ws.cell(r, i, getattr(row, attribute))
                if number_format:
                    cell.number_format = number_format
        ws.freeze_panes = ws.cell(HEADER_ROW + 1, 1)
        self.output = in_memory(wb)
        wb.close()
