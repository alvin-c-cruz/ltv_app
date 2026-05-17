from ...database import get_db
from datetime import datetime, timedelta

from ...term_sheet import StockContract


class GenerateFixings:
    def __init__(self, trade_date):
        self.db = get_db()
        self.trade_date = trade_date
        self.fixings = {}

        self.gather_fixings()

    def gather_fixings(self):
        currencies = get_currency(self.db)
        accounts = get_accounts(self.db)

        def is_holiday(_date, _ccy="HKD"):
            sql = """
                SELECT COUNT(*) FROM tbl_holiday 
                INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
                WHERE tbl_holiday.holi_date=? AND tbl_currency.ccy_id=?
            """
            if self.db.execute(sql, (str(_date)[:10], _ccy)).fetchone()[0]:
                return True
            else:
                return False

        for ccy in currencies:
            # Do not gather fixings if trade_date is a holiday
            if is_holiday(self.trade_date, ccy["ccy_code"]):
                continue

            for account in accounts:
                end_date_to_find = self.trade_date if account["indicative"] == "Yes" else previous_day(
                    self.db, self.trade_date)

                active_contract_refs = [row[0] for row in self.db.execute(
                    "SELECT tbl_stock_contract.ref_num FROM tbl_stock_contract "
                    "INNER JOIN tbl_code ON tbl_code.ref_num = tbl_stock_contract.code_ref "
                    "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref "
                    "WHERE tbl_stock_contract.bank_ref=? "
                    "   AND tbl_stock_contract.status='active' "
                    "   AND tbl_currency.ref_num=? "
                    "ORDER BY tbl_stock_contract.transaction_type, tbl_stock_contract.trade_date",
                    (account["id"], ccy["id"])
                ).fetchall()]

                for contract_ref in active_contract_refs:
                    is_fixing = False
                    ts = StockContract(db=self.db)
                    ts.get(ref_num=contract_ref)
                    ts.__post_init__()
                    ts.get_schedules()

                    # Check if KO
                    if check_ko(self.db, ts, self.trade_date):
                        is_fixing = "KO"
                    # Check if regular fixing
                    elif check_fixing(ts, end_date_to_find):
                        is_fixing = "Regular"

                    if is_fixing:
                        ts_dict = analyze_fixing(ts, end_date_to_find, self.db)
                        ts_dict["contract_ref"] = contract_ref
                        ts_dict["value_date"] = next_day(self.db, self.trade_date)
                        if account["indicative"] == "Yes" and is_fixing == "Regular":
                            ts_dict["value_date"] = next_day(self.db, ts_dict["value_date"])

                        if ccy["ccy_code"] not in self.fixings:
                            self.fixings[ccy["ccy_code"]] = {}

                        if account["bank_code"] not in self.fixings[ccy["ccy_code"]]:
                            self.fixings[ccy["ccy_code"]][account["bank_code"]] = []

                        self.fixings[ccy["ccy_code"]][account["bank_code"]].append(ts_dict)


def get_accounts(db):
    accounts = db.execute(
        "SELECT ref_num, bank_id, indicative FROM tbl_bank_account ORDER BY priority").fetchall()
    return [{"id": x["ref_num"], "bank_code": x["bank_id"], "indicative": x["indicative"]} for x in accounts]


def get_currency(db):
    currency = db.execute(
        "SELECT ref_num, ccy_id FROM tbl_currency ORDER BY priority").fetchall()
    return [{"id": x["ref_num"], "ccy_code": x["ccy_id"]} for x in currency]


def previous_day(db, _date):
    def check_date(end_date):
        end_date_on_record = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=1)

        while True:
            if is_holiday(end_date_on_record):
                end_date_on_record -= timedelta(days=1)
            elif end_date_on_record.isoweekday() in (6, 7):
                end_date_on_record -= timedelta(days=1)
            else:
                break

        return str(end_date_on_record)[:10]

    def is_holiday(_date, ccy="HKD"):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            WHERE tbl_holiday.holi_date=? AND tbl_currency.ccy_id=?
        """
        if db.execute(sql, (str(_date)[:10], ccy)).fetchone()[0]:
            return True
        else:
            return False

    return check_date(_date)


def next_day(db, _date):
    def check_date(end_date):
        end_date_on_record = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)

        while True:
            if is_holiday(end_date_on_record):
                end_date_on_record += timedelta(days=1)
            elif end_date_on_record.isoweekday() in (6, 7):
                end_date_on_record += timedelta(days=1)
            else:
                break

        return str(end_date_on_record)[:10]

    def is_holiday(_date, ccy="HKD"):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            WHERE tbl_holiday.holi_date=? AND tbl_currency.ccy_id=?
        """
        if db.execute(sql, (str(_date)[:10], ccy)).fetchone()[0]:
            return True
        else:
            return False

    return check_date(_date)


def working_day(db, trade_date, ccy):
    def check_date(end_date):
        if is_holiday(end_date):
            return False
        elif end_date.isoweekday() in (6, 7):
            return False
        else:
            return True

    def is_holiday(end_date):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            WHERE tbl_holiday.holi_date=? AND tbl_currency.ccy_id=?
        """
        if db.execute(sql, (str(end_date)[:10], ccy)).fetchone()[0]:
            return True
        else:
            return False

    return check_date(trade_date)


def daterange(start_date, end_date):
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    end_date = end_date + timedelta(days=1)
    for n in range(int((end_date - start_date).days)):
        yield start_date + timedelta(n)


def check_ko(db, ts, trade_date):
    transaction_type = ts.transaction_type
    ko = float(ts.ko)
    code_ref = ts.code_ref
    closing_price = None
    while closing_price is None:
        closing_price = db.execute(
            "SELECT closing_price "
            "FROM tbl_stock_price "
            "WHERE code_ref=? AND trade_date=?", (code_ref, trade_date)).fetchone()
        if closing_price is None:
            trade_date = previous_day(db, trade_date)
    closing_price = closing_price[0]

    if transaction_type == "ACCU":
        if ko <= closing_price:
            return True
    else:
        if ko >= closing_price:
            return True

    return False


def check_fixing(ts, end_date, db=None, ts_dict=None):
    for i, period in enumerate(ts.schedules):
        if period.end_date == end_date:
            if db:
                if len(ts.schedules) == i+1:
                    ts_dict["next_date"] = "Done"
                else:
                    ts_dict["next_date"] = next_day(db, ts.schedules[i+1].end_date)
            return period.ref_num
    return False


def check_ko_fixing(ts, end_date, ts_dict):
    periods = []
    ts_dict["next_date"] = "KO"
    ts_dict["reference"] += " (KO)"
    for i, period in enumerate(ts.schedules):
        if period.end_date >= end_date >= period.start_date:
            periods.append(period.ref_num)
        elif period.start_date >= end_date and period.gtd == "Yes":
            periods.append(period.ref_num)

    return periods


def analyze_fixing(ts, end_date, db):
    ts_dict = ts.as_dict()

    #  Shares per day
    if ts_dict['single'] == ts_dict['double']:
        ts_dict["shares"] = '{:,.0f}'.format(ts_dict['single'])
    else:
        ts_dict["shares"] = '{:,.0f}'.format(ts_dict['single']) + " / " + '{:,.0f}'.format(ts_dict['double'])

    #  Fixings
    ts_dict["fixings"] = []

    is_ko = check_ko(db, ts, end_date)
    if is_ko:
        period_refs = check_ko_fixing(ts, end_date, ts_dict=ts_dict)
    else:
        fixing = check_fixing(ts, end_date, db=db, ts_dict=ts_dict)
        period_refs = [fixing] if fixing else []

    for period_ref in period_refs:
        fixing = db.execute("SELECT * FROM tbl_stock_contract_period WHERE ref_num=?", (period_ref,)).fetchone()

        dates = [date for date in daterange(fixing["start_date"], fixing["end_date"])]

        days_fixing = 0
        days_indicative = 0
        days_double = 0
        shares_fixing = 0
        shares_indicative = 0

        days_closing = []

        for date in dates:
            if working_day(db, date, ts_dict["ccy_id"]):
                closing_price = get_closing(db, ts.code_ref, str(date)[:10])

                if closing_price:
                    sdk = single_double_ko(ts.transaction_type, ts.strike, ts.ko, closing_price)
                    days_closing.append((date, closing_price))
                    if sdk == 2:
                        days_double += 1
                        days_fixing += 1
                        shares_fixing += ts.daily_shares * 2
                    elif sdk == 1:
                        days_fixing += 1
                        shares_fixing += ts.daily_shares
                    else:
                        if fixing["gtd"] == "Yes":
                            days_fixing += 1
                            shares_fixing += ts.daily_shares

                else:
                    previous_closing = None
                    prev_date = str(date)[:10]
                    while previous_closing is None:
                        prev_date = previous_day(db, prev_date)
                        previous_closing = get_closing(db, ts.code_ref, prev_date)
                    days_closing.append((date, previous_closing))
                    sdk = single_double_ko(ts.transaction_type, ts.strike, ts.ko, previous_closing)
                    if sdk == 2:
                        days_indicative += 1
                        shares_indicative += ts.daily_shares * 2
                    elif sdk == 1:
                        days_indicative += 1
                        shares_indicative += ts.daily_shares
                    else:
                        if fixing["gtd"] == "Yes":
                            days_fixing += 1
                            shares_fixing += ts.daily_shares

        period_dict = {
            "period_ref": period_ref,
            "start_date": fixing["start_date"],
            "end_date": fixing["end_date"],
            "shares_indicative": shares_indicative,
            "shares_fixing": shares_fixing,
            "days_indicative": days_indicative,
            "days_fixing": days_fixing,
            "days_double": days_double,
            "days_closing": days_closing
        }

        ts_dict["fixings"].append(period_dict)

    days_fixing = 0
    days_indicative = 0
    days_double = 0
    shares_fixing = 0
    shares_indicative = 0

    days_closing = []
    for fixing in ts_dict["fixings"]:
        days_fixing += fixing["days_fixing"]
        days_indicative += fixing["days_indicative"]
        days_double += fixing["days_double"]
        shares_fixing += fixing["shares_fixing"]
        shares_indicative += fixing["shares_indicative"]
        days_closing += fixing["days_closing"]

    ts_dict["days_fixing"] = days_fixing
    ts_dict["days_indicative"] = days_indicative
    ts_dict["days_double"] = days_double
    ts_dict["shares_fixing"] = shares_fixing
    ts_dict["shares_indicative"] = shares_indicative
    ts_dict["days_closing"] = days_closing

    return ts_dict


def get_closing(db, code_ref, trade_date):
    closing = db.execute(
        "SELECT closing_price "
        "FROM tbl_stock_price "
        "WHERE code_ref=? AND trade_date=?", (code_ref, trade_date)).fetchone()

    return closing[0] if closing is not None else None


def single_double_ko(transaction_type, strike, ko, closing):
    strike = float(strike)
    ko = float(ko)
    if transaction_type == "ACCU":
        if ko <= closing:
            return 0
        elif strike >= closing:
            return 2
        else:
            return 1
    else:
        if ko >= closing:
            return 0
        elif strike <= closing:
            return 2
        else:
            return 1

