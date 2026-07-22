from openpyxl import Workbook
import os


class CreateExcel:
    def __init__(self, path: str, start_date: str, end_date: str, db):
        self.filename = os.path.join(path, f"{start_date}_to_{end_date} dividends.xlsx")
        self.wb = Workbook()
        self.wb.remove(self.wb.active)  # drop the default blank sheet

        self.start_date = start_date
        self.end_date = end_date
        self.db = db

        self.create()

        self.wb.save(self.filename)
        self.wb.close()

    def bank_accounts(self):
        sql = "SELECT ref_num, bank_id, bank_name FROM tbl_bank_account ORDER BY priority;"
        return self.db.execute(sql).fetchall()

    def dividends_for_bank(self, bank_ref):
        sql = """
        SELECT
            tbl_code.stock_name,
            tbl_code.code AS stock_code,
            tbl_cash_dividends.nominal,
            tbl_cash_dividends.declaration_date,
            tbl_cash_dividends.ex_date,
            tbl_cash_dividends.record_date,
            tbl_cash_dividends.pay_out,
            tbl_currency.ccy_id AS ccy_code,
            tbl_cash_dividends.dividends_per_share,
            tbl_cash_dividends.tax,
            tbl_cash_dividends.charges,
            tbl_cash_dividends.status
        FROM tbl_cash_dividends
        INNER JOIN tbl_code ON tbl_code.ref_num = tbl_cash_dividends.stock_id
        INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_cash_dividends.ccy_id
        WHERE tbl_cash_dividends.bank_id = ?
          AND tbl_cash_dividends.ex_date >= ? AND tbl_cash_dividends.ex_date <= ?
        ORDER BY tbl_cash_dividends.ex_date;
        """
        return self.db.execute(sql, (bank_ref, self.start_date, self.end_date)).fetchall()

    def create(self):
        headers = [
            "Stock Name", "Code", "Quantity", "Declaration Date", "Ex Date",
            "Record Date", "Pay-Out Date", "Ccy", "Div/Share", "Gross Amount",
            "Tax/Charges", "Net Amount", "Status",
        ]
        for account in self.bank_accounts():
            ws = self.wb.create_sheet(account["bank_id"])
            ws.append(headers)

            for row in self.dividends_for_bank(account["ref_num"]):
                gross = row["nominal"] * row["dividends_per_share"]
                net = gross - row["tax"] - row["charges"]
                ws.append([
                    row["stock_name"],
                    row["stock_code"],
                    row["nominal"],
                    row["declaration_date"] or "",
                    row["ex_date"],
                    row["record_date"] or "",
                    row["pay_out"],
                    row["ccy_code"],
                    row["dividends_per_share"],
                    round(gross, 2),
                    round(row["tax"] + row["charges"], 2),
                    round(net, 2),
                    row["status"],
                ])
