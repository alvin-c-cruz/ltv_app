from ..models import accumulate_position


class TradesDoneAverage:
    def __init__(self, db, trade_date, code, bank_id):
        transactions = get_transactions(db, trade_date, code, bank_id)
        rows = [
            r for r in transactions
            if not (r['trade_date'] == trade_date and "Transfer" in r['transaction_type'])
        ]
        balance, cost_to_date, last_average = accumulate_position(rows)
        average = cost_to_date / balance if balance > 0 else 0
        self.average = average if average else last_average


def get_transactions(db, trade_date, code, bank_id):
    sql = "SELECT transaction_basis FROM tbl_bank_account WHERE bank_id = ?;"
    transaction_basis = db.execute(sql, (bank_id, )).fetchone()[0]

    sql = "SELECT * FROM tbl_transaction " \
          "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_transaction.code_ref " \
          "INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_transaction.bank_ref " \
          "INNER JOIN tbl_transaction_type " \
          "     ON tbl_transaction_type.transaction_type = tbl_transaction.transaction_type " \
          "WHERE tbl_code.code = ? AND tbl_bank_account.bank_id = ? AND tbl_transaction.trade_date <= ?" \
          f"ORDER BY tbl_transaction.{transaction_basis}, tbl_transaction_type.priority " \
          f";"
    transactions = db.execute(sql, (code, bank_id, trade_date)).fetchall()

    return transactions
