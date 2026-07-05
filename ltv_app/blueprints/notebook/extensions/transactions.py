TRADE_SQL = "SELECT " \
            "   tbl_currency.ccy_id, " \
            "   tbl_bank_account.bank_id, " \
            "   tbl_bank_account.bank_name, " \
            "   tbl_code.stock_name, " \
            "   tbl_code.code, " \
            "   tbl_transaction.transaction_type, " \
            "   tbl_transaction.quantity, " \
            "   tbl_transaction.price, " \
            "   tbl_transaction.spot, " \
            "   tbl_transaction.ko " \
            "FROM tbl_transaction " \
            "INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_transaction.bank_ref " \
            "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_transaction.code_ref " \
            "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref " \
            "INNER JOIN tbl_transaction_type " \
            "   ON tbl_transaction_type.transaction_type = tbl_transaction.transaction_type " \
            "WHERE tbl_transaction.trade_date = ? " \
            "   AND tbl_transaction.transaction_type NOT IN ('Transfer-Out', 'Transfer-In') " \
            "ORDER BY " \
            "   tbl_currency.priority, " \
            "   tbl_bank_account.priority, " \
            "   tbl_code.code, " \
            "   tbl_transaction_type.priority"


CONTRACT_SQL = "SELECT " \
            "   tbl_currency.ccy_id, " \
            "   tbl_bank_account.bank_id, " \
            "   tbl_bank_account.bank_name, " \
            "   tbl_code.stock_name, " \
            "   tbl_code.code, " \
            "   tbl_stock_contract.transaction_type, " \
            "   tbl_stock_contract.daily_shares, " \
            "   tbl_stock_contract.leveraged, " \
            "   tbl_stock_contract.spot, " \
            "   tbl_stock_contract.strike_rate, " \
            "   tbl_stock_contract.ko_rate, " \
            "   tbl_stock_contract.tenor, " \
            "   tbl_stock_contract.gtd " \
            "FROM tbl_stock_contract " \
            "INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_stock_contract.bank_ref " \
            "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_stock_contract.code_ref " \
            "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref " \
            "WHERE tbl_stock_contract.trade_date = ? " \
            "ORDER BY " \
            "   tbl_currency.priority, " \
            "   tbl_bank_account.priority, " \
            "   tbl_code.code, " \
            "   tbl_stock_contract.transaction_type "


def get_transactions(db, trade_date):
    transactions = {}

    contracts = db.execute(CONTRACT_SQL, (trade_date,)).fetchall()
    trades = db.execute(TRADE_SQL, (trade_date,)).fetchall()

    for group in (trades, contracts):
        for row in group:
            ccy = row["ccy_id"]
            bank_name = row["bank_name"]
            code = row["code"]
            transaction_type = row["transaction_type"]

            if ccy not in transactions:
                transactions[ccy] = {}

            if bank_name not in transactions[ccy]:
                transactions[ccy][bank_name] = {}

            if code not in transactions[ccy][bank_name]:
                transactions[ccy][bank_name][code] = {}

            if transaction_type not in transactions[ccy][bank_name][code]:
                transactions[ccy][bank_name][code][transaction_type] = []

            transactions[ccy][bank_name][code][transaction_type].append(row)

    ccys = [x[0] for x in db.execute("SELECT ccy_id FROM tbl_currency ORDER BY priority").fetchall()]
    bank_names = [x[0] for x in db.execute("SELECT bank_name FROM tbl_bank_account ORDER BY priority").fetchall()]

    sorted_transactions = {}
    for _ccy in ccys:
        if _ccy in transactions:
            sorted_transactions[_ccy] = {}

            for _bank_name in bank_names:
                if _bank_name in transactions[_ccy]:
                    sorted_transactions[_ccy][_bank_name] = transactions[_ccy][_bank_name]

    return sorted_transactions


TRANSFER_SQL = """
    SELECT
        out_t.ref_num       AS out_ref,
        out_bank.bank_name  AS out_bank,
        out_bank.bank_id    AS out_bank_id,
        in_bank.bank_name   AS in_bank,
        in_bank.bank_id     AS in_bank_id,
        C.stock_name,
        C.code,
        CY.ccy_id,
        ABS(out_t.quantity) AS quantity
    FROM tbl_transaction out_t
    INNER JOIN tbl_bank_account out_bank ON out_bank.ref_num = out_t.bank_ref
    INNER JOIN tbl_bank_account in_bank  ON in_bank.ref_num  = out_t.counter_bank_ref
    INNER JOIN tbl_code C      ON C.ref_num  = out_t.code_ref
    INNER JOIN tbl_currency CY ON CY.ref_num = C.ccy_ref
    WHERE out_t.transaction_type = 'Transfer-Out'
      AND out_t.counter_bank_ref IS NOT NULL
      AND out_t.trade_date = ?
    ORDER BY C.code, out_t.ref_num
"""


def get_transfers(db, trade_date):
    rows = db.execute(TRANSFER_SQL, (trade_date,)).fetchall()
    return [dict(r) for r in rows]
