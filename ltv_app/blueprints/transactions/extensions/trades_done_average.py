class TradesDoneAverage:
    def __init__(self, db, trade_date, code, bank_id):
        transactions = get_transactions(db, trade_date, code, bank_id)

        self.average = get_average(transactions, trade_date)


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


def get_average(transactions, trade_date):
    balance = 0
    cost_to_date = 0.0
    average = 0
    last_average = 0

    for row in transactions:
        row_date = row['trade_date']
        transaction_type = row['transaction_type']
        quantity = row['quantity']
        price = row['price']
        charges = row['brokerage'] + row['commission'] + row['foreign_charge'] + row['stamp_duty'] + row['misc']
        amount = quantity * price + charges

        if row_date == trade_date and "Transfer" in transaction_type:
            continue

        if quantity > 0:
            if balance > 0:
                cost_to_date += amount
            elif balance == 0:
                cost_to_date += amount
            elif balance < 0:
                if balance + quantity == 0:
                    cost_to_date = 0
                elif balance + quantity < 0:
                    cost_to_date = 0
                else:
                    cost_to_date = (balance + quantity) / quantity * amount

        else:
            if balance > 0:
                if balance - abs(quantity) > 0:
                    cost_to_date -= cost_to_date * abs(quantity) / balance
                else:
                    cost_to_date = 0
            else:
                cost_to_date = 0

        balance += quantity
        average = cost_to_date / balance if balance > 0 else 0
        if average != 0:
            last_average = average

    return average if average else last_average
