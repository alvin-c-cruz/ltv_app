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
        db = self.db
        currencies = get_currency(db)
        accounts = get_accounts(db)

        # Load ALL holidays once (replaces per-date DB queries)
        holidays = {
            (str(r['holi_date'])[:10], r['ccy_id'])
            for r in db.execute(
                "SELECT holi_date, tbl_currency.ccy_id "
                "FROM tbl_holiday "
                "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_holiday.ccy_ref"
            ).fetchall()
        }

        # Load ALL closing prices once (replaces per-date DB queries)
        closing_cache = {
            (r['code_ref'], str(r['trade_date'])[:10]): r['closing_price']
            for r in db.execute(
                "SELECT code_ref, trade_date, closing_price FROM tbl_stock_price"
            ).fetchall()
        }

        # In-memory helpers — no DB access
        def is_holiday(date, ccy="HKD"):
            return (str(date)[:10], ccy) in holidays

        def prev_day(date):
            d = datetime.strptime(str(date)[:10], '%Y-%m-%d') - timedelta(days=1)
            while is_holiday(d) or d.isoweekday() in (6, 7):
                d -= timedelta(days=1)
            return str(d)[:10]

        def next_day(date):
            d = datetime.strptime(str(date)[:10], '%Y-%m-%d') + timedelta(days=1)
            while is_holiday(d) or d.isoweekday() in (6, 7):
                d += timedelta(days=1)
            return str(d)[:10]

        def is_working_day(date, ccy="HKD"):
            d = date if isinstance(date, datetime) else datetime.strptime(str(date)[:10], '%Y-%m-%d')
            return not is_holiday(d, ccy) and d.isoweekday() not in (6, 7)

        def get_closing(code_ref, date):
            return closing_cache.get((code_ref, str(date)[:10]))

        def get_closing_fallback(code_ref, date):
            d = str(date)[:10]
            price = get_closing(code_ref, d)
            while price is None:
                d = prev_day(d)
                price = get_closing(code_ref, d)
            return price

        for ccy in currencies:
            if is_holiday(self.trade_date, ccy["ccy_code"]):
                continue

            for account in accounts:
                end_date_to_find = (
                    self.trade_date if account["indicative"] == "Yes"
                    else prev_day(self.trade_date)
                )

                active_contract_refs = [row[0] for row in db.execute(
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
                    ts = StockContract(db=db)
                    ts.get(ref_num=contract_ref)
                    ts.__post_init__()
                    ts.get_schedules()

                    closing = get_closing_fallback(ts.code_ref, self.trade_date)
                    if ts.transaction_type == "ACCU":
                        is_ko = float(ts.ko) <= closing
                    else:
                        is_ko = float(ts.ko) >= closing

                    if is_ko:
                        is_fixing = "KO"
                    elif check_fixing(ts, end_date_to_find):
                        is_fixing = "Regular"
                    else:
                        is_fixing = False

                    if is_fixing:
                        ts_dict = analyze_fixing(
                            ts, end_date_to_find, db,
                            is_working_day, get_closing, get_closing_fallback,
                            prev_day, next_day
                        )
                        ts_dict["contract_ref"] = contract_ref
                        ts_dict["value_date"] = next_day(self.trade_date)
                        if account["indicative"] == "Yes" and is_fixing == "Regular":
                            ts_dict["value_date"] = next_day(ts_dict["value_date"])

                        if ccy["ccy_code"] not in self.fixings:
                            self.fixings[ccy["ccy_code"]] = {}
                        if account["bank_code"] not in self.fixings[ccy["ccy_code"]]:
                            self.fixings[ccy["ccy_code"]][account["bank_code"]] = []
                        self.fixings[ccy["ccy_code"]][account["bank_code"]].append(ts_dict)


def get_accounts(db):
    accounts = db.execute(
        "SELECT ref_num, bank_id, indicative FROM tbl_bank_account ORDER BY priority"
    ).fetchall()
    return [{"id": x["ref_num"], "bank_code": x["bank_id"], "indicative": x["indicative"]} for x in accounts]


def get_currency(db):
    currency = db.execute(
        "SELECT ref_num, ccy_id FROM tbl_currency ORDER BY priority"
    ).fetchall()
    return [{"id": x["ref_num"], "ccy_code": x["ccy_id"]} for x in currency]


def daterange(start_date, end_date):
    start = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")
    end   = datetime.strptime(str(end_date)[:10],   "%Y-%m-%d") + timedelta(days=1)
    for n in range(int((end - start).days)):
        yield start + timedelta(n)


def check_fixing(ts, end_date, db=None, ts_dict=None, next_day=None):
    for i, period in enumerate(ts.schedules):
        if period.end_date == end_date:
            if db and ts_dict is not None and next_day is not None:
                if len(ts.schedules) == i + 1:
                    ts_dict["next_date"] = "Done"
                else:
                    ts_dict["next_date"] = next_day(ts.schedules[i + 1].end_date)
            return period.ref_num
    return False


def check_ko_fixing(ts, end_date, ts_dict):
    periods = []
    ts_dict["next_date"] = "KO"
    ts_dict["reference"] += " (KO)"
    for period in ts.schedules:
        if period.end_date >= end_date >= period.start_date:
            periods.append(period.ref_num)
        elif period.start_date >= end_date and period.gtd == "Yes":
            periods.append(period.ref_num)
    return periods


def analyze_fixing(ts, end_date, db, is_working_day, get_closing, get_closing_fallback, prev_day, next_day):
    ts_dict = ts.as_dict()

    ts_dict["shares"] = (
        '{:,.0f}'.format(ts_dict['single'])
        if ts_dict['single'] == ts_dict['double']
        else '{:,.0f}'.format(ts_dict['single']) + " / " + '{:,.0f}'.format(ts_dict['double'])
    )

    ts_dict["fixings"] = []

    closing_at_end = get_closing_fallback(ts.code_ref, end_date)
    if ts.transaction_type == "ACCU":
        is_ko = float(ts.ko) <= closing_at_end
    else:
        is_ko = float(ts.ko) >= closing_at_end

    if is_ko:
        period_refs = check_ko_fixing(ts, end_date, ts_dict=ts_dict)
    else:
        fixing = check_fixing(ts, end_date, db=db, ts_dict=ts_dict, next_day=next_day)
        period_refs = [fixing] if fixing else []

    for period_ref in period_refs:
        fixing = db.execute(
            "SELECT * FROM tbl_stock_contract_period WHERE ref_num=?", (period_ref,)
        ).fetchone()

        days_fixing = days_indicative = days_double = 0
        shares_fixing = shares_indicative = 0
        days_closing = []

        for date in daterange(fixing["start_date"], fixing["end_date"]):
            if is_working_day(date, ts_dict["ccy_id"]):
                closing_price = get_closing(ts.code_ref, str(date)[:10])

                if closing_price is not None:
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
                    # Indicative day — use most recent available closing
                    prev_date = prev_day(str(date)[:10])
                    prev_closing = get_closing(ts.code_ref, prev_date)
                    while prev_closing is None:
                        prev_date = prev_day(prev_date)
                        prev_closing = get_closing(ts.code_ref, prev_date)

                    days_closing.append((date, prev_closing))
                    sdk = single_double_ko(ts.transaction_type, ts.strike, ts.ko, prev_closing)
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

        ts_dict["fixings"].append({
            "period_ref":        period_ref,
            "start_date":        fixing["start_date"],
            "end_date":          fixing["end_date"],
            "shares_indicative": shares_indicative,
            "shares_fixing":     shares_fixing,
            "days_indicative":   days_indicative,
            "days_fixing":       days_fixing,
            "days_double":       days_double,
            "days_closing":      days_closing,
        })

    # Aggregate across all periods
    days_fixing = days_indicative = days_double = 0
    shares_fixing = shares_indicative = 0
    days_closing = []
    for p in ts_dict["fixings"]:
        days_fixing      += p["days_fixing"]
        days_indicative  += p["days_indicative"]
        days_double      += p["days_double"]
        shares_fixing    += p["shares_fixing"]
        shares_indicative += p["shares_indicative"]
        days_closing     += p["days_closing"]

    ts_dict["days_fixing"]      = days_fixing
    ts_dict["days_indicative"]  = days_indicative
    ts_dict["days_double"]      = days_double
    ts_dict["shares_fixing"]    = shares_fixing
    ts_dict["shares_indicative"] = shares_indicative
    ts_dict["days_closing"]     = days_closing

    return ts_dict


def single_double_ko(transaction_type, strike, ko, closing):
    strike = float(strike)
    ko     = float(ko)
    if transaction_type == "ACCU":
        if ko <= closing:   return 0
        elif strike >= closing: return 2
        else:               return 1
    else:
        if ko >= closing:   return 0
        elif strike <= closing: return 2
        else:               return 1
