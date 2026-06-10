from datetime import datetime

from .trades_done_average import TradesDoneAverage


class TradesDoneReport:
    """Builds the data for the printable Trades Done page — the HTML
    equivalent of DownloadTradesDoneWithGainLoss, with the Excel formulas
    computed in Python. Gain/loss applies only to Sell (Spot) blocks."""

    def __init__(self, db, trade_date, trade_summary):
        self.trade_date = trade_date
        self.date_label = datetime.strptime(trade_date, "%Y-%m-%d").strftime("%B %d, %Y")
        self.accus = self._term_sheet_rows(trade_summary.accus)
        self.decus = self._term_sheet_rows(trade_summary.decus)
        self.blocks = self._transaction_blocks(db, trade_date, trade_summary.transactions)

    def _term_sheet_rows(self, term_sheets):
        rows = []
        for ccy in term_sheets:
            rows.extend(term_sheets[ccy])
        return rows

    def _transaction_blocks(self, db, trade_date, transactions):
        blocks = []
        for ccy in transactions:
            for transaction_type in transactions[ccy]:
                if "Transfer" in transaction_type:
                    continue
                blocks.append(self._build_block(db, trade_date, ccy, transaction_type,
                                                transactions[ccy][transaction_type]))
        return blocks

    def _build_block(self, db, trade_date, ccy, transaction_type, by_bank):
        is_buy = "Buy" in transaction_type
        is_sell_spot = transaction_type == "Sell (Spot)"

        banks = []
        block_shares = 0.0
        block_amount = 0.0
        trade_total = False
        gain_values = []

        for bank_name in by_bank:
            rows = []
            bank_proceeds = bank_cost = bank_gain = 0.0
            for stock_name in by_bank[bank_name]:
                trades = by_bank[bank_name][stock_name]
                trade_count = len(trades)
                if trade_count > 1:
                    trade_total = True
                for i_trade, trade in enumerate(trades):
                    quantity = float(trade["quantity"].replace(",", ""))
                    price = float(trade["price"].replace(",", ""))
                    amount = quantity * price
                    row = {
                        "bank_name": bank_name,
                        "stock_name": stock_name,
                        "transaction_type": transaction_type,
                        "price": price,
                        "quantity": quantity,
                        "amount": amount,
                        "average": None,
                        "cost": None,
                        "gain_loss": None,
                        "pct": None,
                    }

                    if is_buy:
                        if i_trade + 1 == trade_count:
                            row["average"] = TradesDoneAverage(
                                db=db, trade_date=trade_date,
                                code=trade["code"], bank_id=trade["bank_id"]).average
                    elif is_sell_spot:
                        average = TradesDoneAverage(
                            db=db, trade_date=trade_date,
                            code=trade["code"], bank_id=trade["bank_id"]).average
                        cost = quantity * average
                        gain = amount - cost
                        row["cost"] = cost
                        row["gain_loss"] = gain
                        row["pct"] = gain / cost if cost else None
                        bank_proceeds += amount
                        bank_cost += cost
                        bank_gain += gain
                        gain_values.append(gain)

                    rows.append(row)
                    block_shares += quantity
                    block_amount += amount

            bank = {"bank_name": bank_name, "rows": rows, "subtotal": None}
            if is_sell_spot and rows:
                bank["subtotal"] = {
                    "proceeds": bank_proceeds,
                    "cost": bank_cost,
                    "gain_loss": bank_gain,
                    "pct": bank_gain / bank_cost if bank_cost else None,
                }
            banks.append(bank)

        block = {
            "ccy": ccy,
            "label": "BUY" if is_buy else "SELL",
            "transaction_type": transaction_type,
            "is_buy": is_buy,
            "is_sell_spot": is_sell_spot,
            "banks": banks,
            "show_total": len(by_bank) > 1 or trade_total,
            "total_shares": block_shares,
            "total_amount": block_amount,
            "gain_header": None,
            "pct_header": None,
        }

        if is_sell_spot and gain_values:
            has_gain = any(v >= 0 for v in gain_values)
            has_loss = any(v < 0 for v in gain_values)
            label = "Gain / Loss" if (has_gain and has_loss) else ("Gain" if has_gain else "Loss")
            block["gain_header"] = f"{label} {ccy}"
            block["pct_header"] = f"% {label}"

        return block
