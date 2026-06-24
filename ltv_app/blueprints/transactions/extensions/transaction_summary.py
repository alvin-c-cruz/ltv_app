from dataclasses import dataclass


class TransactionSummary:
    def __init__(self, db, trade_date):
        self.accus = self.get_term_sheets(db, trade_date, "ACCU")
        self.decus = self.get_term_sheets(db, trade_date, "DECU")

        self.transactions = {}
        self.get_transactions(db, trade_date)

        self.short_transactions = {}
        self.get_short_transactions(db, trade_date)

        self.transfers = self.get_transfers(db, trade_date)

    def is_empty(self):
        return False if self.accus or self.decus or self.transactions or self.transfers else True

    def get_transactions(self, db, trade_date):
        sql = """
          SELECT
            t.ref_num,
            currency.ccy_id,
            bank.bank_id,
            bank.bank_name,
            stock.stock_name,
            stock.code,
            t.transaction_type,
            t.quantity,
            t.price,
            t.brokerage, t.commission, t.foreign_charge, t.stamp_duty, t.misc,
            t.locked
          FROM tbl_transaction AS t
          INNER JOIN tbl_bank_account AS bank ON bank.ref_num = t.bank_ref
          INNER JOIN tbl_code AS stock ON stock.ref_num = t.code_ref
          INNER JOIN tbl_currency AS currency ON currency.ref_num = stock.ccy_ref
          INNER JOIN tbl_transaction_type ON tbl_transaction_type.transaction_type = t.transaction_type
          WHERE trade_date=?
            AND (t.transaction_type LIKE "%Spot%"
                OR t.transaction_type LIKE "%Short%"
                OR t.transaction_type LIKE "Transfer%"
                OR t.transaction_type = "Stock Dividend"
                OR t.transaction_type LIKE "Return%"
                OR t.transaction_type LIKE "Borrow%")
          ORDER BY currency.priority, tbl_transaction_type.priority, bank.priority, stock.code
          ;"""

        data = db.execute(sql, (trade_date,)).fetchall()

        for row in data:
            ccy_id = row['ccy_id']
            transaction_type = row['transaction_type']

            bank_name = row['bank_name']
            stock = f"{row['stock_name']} ({row['code']})"
            ref_num = row['ref_num']
            quantity = '{:,.0f}'.format(abs(row['quantity']))
            price = '{:,.4f}'.format(row['price'])
            amt = abs(row['quantity']) * row['price']
            charges = (row['brokerage'] or 0) + (row['commission'] or 0) + (row['foreign_charge'] or 0) + (row['stamp_duty'] or 0) + (row['misc'] or 0)
            net = amt - charges

            if ccy_id not in self.transactions:
                self.transactions[ccy_id] = {}

            if transaction_type not in self.transactions[ccy_id]:
                self.transactions[ccy_id][transaction_type] = {}

            if bank_name not in self.transactions[ccy_id][transaction_type]:
                self.transactions[ccy_id][transaction_type][bank_name] = {}

            if stock not in self.transactions[ccy_id][transaction_type][bank_name]:
                self.transactions[ccy_id][transaction_type][bank_name][stock] = []

            self.transactions[ccy_id][transaction_type][bank_name][stock].append({
                "ref_num":    ref_num,
                "bank_id":    row["bank_id"],
                "code":       row["code"],
                "quantity":   quantity,
                "price":      price,
                "amount":     '{:,.2f}'.format(amt),
                "charges":    '{:,.2f}'.format(charges),
                "net_amount": '{:,.2f}'.format(net),
                "locked":     row["locked"],
            })

    def get_short_transactions(self, db, trade_date):
        sql = """
          SELECT
            t.ref_num,
            currency.ccy_id,
            bank.bank_id,
            bank.bank_name,
            stock.stock_name,
            stock.code,
            t.transaction_type,
            t.quantity,
            t.price,
            t.brokerage, t.commission, t.foreign_charge, t.stamp_duty, t.misc,
            t.locked
          FROM tbl_transaction_short AS t
          INNER JOIN tbl_bank_account AS bank ON bank.ref_num = t.bank_ref
          INNER JOIN tbl_code AS stock ON stock.ref_num = t.code_ref
          INNER JOIN tbl_currency AS currency ON currency.ref_num = stock.ccy_ref
          INNER JOIN tbl_transaction_type ON tbl_transaction_type.transaction_type = t.transaction_type
          WHERE trade_date=?
            AND (t.transaction_type LIKE "%Spot%"
                OR t.transaction_type LIKE "%Short%"
                OR t.transaction_type LIKE "Return%"
                OR t.transaction_type LIKE "Borrow%")
          ORDER BY currency.priority, tbl_transaction_type.priority, bank.priority, stock.code
          ;"""

        data = db.execute(sql, (trade_date,)).fetchall()

        for row in data:
            ccy_id = row['ccy_id']
            transaction_type = row['transaction_type']

            bank_name = row['bank_name']
            stock = f"{row['stock_name']} ({row['code']})"
            ref_num = row['ref_num']
            quantity = '{:,.0f}'.format(abs(row['quantity']))
            price = '{:,.4f}'.format(row['price'])
            amt = abs(row['quantity']) * row['price']
            charges = (row['brokerage'] or 0) + (row['commission'] or 0) + (row['foreign_charge'] or 0) + (row['stamp_duty'] or 0) + (row['misc'] or 0)
            net = amt - charges

            if ccy_id not in self.short_transactions:
                self.short_transactions[ccy_id] = {}

            if transaction_type not in self.short_transactions[ccy_id]:
                self.short_transactions[ccy_id][transaction_type] = {}

            if bank_name not in self.short_transactions[ccy_id][transaction_type]:
                self.short_transactions[ccy_id][transaction_type][bank_name] = {}

            if stock not in self.short_transactions[ccy_id][transaction_type][bank_name]:
                self.short_transactions[ccy_id][transaction_type][bank_name][stock] = []

            self.short_transactions[ccy_id][transaction_type][bank_name][stock].append({
                "ref_num":    ref_num,
                "bank_id":    row["bank_id"],
                "code":       row["code"],
                "quantity":   quantity,
                "price":      price,
                "amount":     '{:,.2f}'.format(amt),
                "charges":    '{:,.2f}'.format(charges),
                "net_amount": '{:,.2f}'.format(net),
                "locked":     row["locked"],
            })

    def get_transfers(self, db, trade_date):
        sql = """
          SELECT
            currency.ccy_id,
            bank.bank_id,
            bank.bank_name,
            counter_bank.bank_id AS counter_bank_id,
            counter_bank.bank_name AS counter_bank_name,
            stock.stock_name,
            stock.code,
            ABS(t.quantity) AS quantity,
            t.price
          FROM tbl_transaction AS t
          INNER JOIN tbl_bank_account AS bank ON bank.ref_num = t.bank_ref
          LEFT JOIN tbl_bank_account AS counter_bank ON counter_bank.ref_num = t.counter_bank_ref
          INNER JOIN tbl_code AS stock ON stock.ref_num = t.code_ref
          INNER JOIN tbl_currency AS currency ON currency.ref_num = stock.ccy_ref
          WHERE t.trade_date = ?
            AND t.transaction_type = 'Transfer-Out'
          ORDER BY currency.priority, bank.priority, stock.code
          ;"""
        data = db.execute(sql, (trade_date,)).fetchall()
        transfers = []
        for i, row in enumerate(data, 1):
            transfers.append({
                'seq': i,
                'ccy_id': row['ccy_id'],
                'bank_id': row['bank_id'],
                'bank_name': row['bank_name'],
                'counter_bank_id': row['counter_bank_id'] or '',
                'counter_bank_name': row['counter_bank_name'] or '',
                'stock_name': row['stock_name'],
                'code': row['code'],
                'quantity': row['quantity'],
            })
        return transfers

    def get_term_sheets(self, db, trade_date, _type):
        term_sheets = {}

        sql = "SELECT " \
              " c.ref_num as contract_ref, " \
              " c.trade_date, " \
              " c.start_date, " \
              " a.bank_name, " \
              " c.transaction_type, " \
              " s.code, " \
              " s.stock_name, " \
              " c.daily_shares, " \
              " c.leveraged, " \
              " c.spot, " \
              " c.strike_rate, " \
              " c.ko_rate, " \
              " c.tenor, " \
              " c.gtd, " \
              " c.locked, " \
              " tbl_currency.ccy_id " \
              "FROM tbl_stock_contract as c " \
              "INNER JOIN tbl_bank_account as a ON a.ref_num = c.bank_ref " \
              "INNER JOIN tbl_code as s ON s.ref_num = c.code_ref " \
              "INNER JOIN tbl_currency ON tbl_currency.ref_num = s.ccy_ref " \
              "WHERE trade_date = ? " \
              "  AND transaction_type = ? " \
              "ORDER BY tbl_currency.priority, a.priority, s.code " \
              ";"

        data = db.execute(sql, (trade_date, _type)).fetchall()

        for row in data:
            ccy = row["ccy_id"]

            if ccy not in term_sheets:
                term_sheets[ccy] = []

            ts = term_sheet(
               id=row["contract_ref"],
               bank_name=row["bank_name"],
               code=row["code"],
               strike_rate=row["strike_rate"],
               ko_rate=row["ko_rate"],
               stock_name=row["stock_name"] + f" ({row['code']})",
               shares= f'{"{:,.0f}".format(row["daily_shares"])} / {"{:,.0f}".format(row["daily_shares"] * 2)}' if row["leveraged"] == "Yes" else "{:,.0f}".format(row["daily_shares"]),
               spot="{:,.4f}".format(row["spot"]),
               strike=f'{"{:,.4f}".format(row["spot"]*row["strike_rate"]/100)} ({"{:,.2f}".format(row["strike_rate"])}%)',
               ko=f'{"{:,.4f}".format(row["spot"] * row["ko_rate"] / 100)} ({"{:,.2f}".format(row["ko_rate"])}%)',
               tenor=row["tenor"],
               gtd=row["gtd"],
               locked=row["locked"],
            )
            term_sheets[ccy].append(ts)

        return term_sheets


@dataclass
class term_sheet:
    id: int
    code: str
    bank_name: str
    stock_name: str
    shares: str
    spot: str
    strike_rate: str
    strike: str
    ko_rate: str
    ko: str
    tenor: str
    gtd: str
    locked: int = 0
