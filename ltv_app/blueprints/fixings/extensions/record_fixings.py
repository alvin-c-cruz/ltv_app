class RecordFixings:
    def __init__(self, db, fixing_data, trade_date):
        for ccy, accounts in fixing_data.items():
            for account, fixings in accounts.items():
                for fixing in fixings:
                    contract_ref = fixing["contract_ref"]
                    spot = fixing["spot"]
                    ko = fixing["ko"]
                    value_date = fixing["value_date"]
                    bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account WHERE bank_id=?", (account,)).fetchone()[0]
                    code_ref = db.execute("SELECT ref_num FROM tbl_code WHERE code=?", (fixing["code"],)).fetchone()[0]
                    transaction_type = fixing["transaction_type"]
                    quantity = fixing["shares_fixing"] + fixing["shares_indicative"]
                    price = fixing["strike"]

                    if transaction_type == "DECU":
                        quantity = quantity * -1

                    if fixing["next_date"] == "KO":
                        if transaction_type == "ACCU":
                            transaction_type = "Buy (Accu-KO)"
                        else:
                            transaction_type = "Sell (Decu-KO)"
                    else:
                        if transaction_type == "ACCU":
                            transaction_type = "Buy (Accu)"
                        else:
                            transaction_type = "Sell (Decu)"

                    sql = "INSERT INTO tbl_transaction " \
                          "(trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, " \
                          "brokerage, commission, foreign_charge, stamp_duty, misc, spot, ko) " \
                          "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, ?, ?);"
                    args = (trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, spot, ko)

                    db.execute(sql, args)
                    db.commit()

                    if fixing["next_date"] == "KO":
                        sql = "UPDATE tbl_stock_contract SET status='KO' WHERE ref_num=?;"
                        args = (contract_ref, )
                    else:
                        for period in fixing["fixings"]:
                            period_ref = period["period_ref"]
                            received = period["shares_fixing"] + period["shares_indicative"]

                            sql = "UPDATE tbl_stock_contract_period SET received=? WHERE ref_num=?;"
                            args = (received, period_ref)

                    db.execute(sql, args)
                    db.commit()
