from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from .. data_model import Model


def _to_int(value):
    """Coerce a period's numeric column (received/days) to int.

    `tbl_stock_contract_period.received` and `.days` hold mixed types in the
    live DB — int, numeric string, comma-formatted string like '24,000', or
    empty. Strip commas/whitespace (matching the convention used in the
    transactions download extensions) and treat blank/None as 0.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if value == "":
            return 0
    return int(float(value))


def _normalize_period_value(value):
    """Coerce a period column for *storage*: strip commas/whitespace and store
    as int, but preserve blank/None as the empty-string marker.

    Mirrors `_to_int` (which guards reads of legacy mixed-type data) but keeps
    un-received periods as "" rather than 0, matching the existing column
    convention and avoiding needless row churn on edit-save.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if value == "":
            return ""
    return int(float(value))


@dataclass
class StockContract(Model):
    table_name: str = field(repr=False, default="tbl_stock_contract")
    ref_num: int = None
    reference: str = ""
    bank_ref: int = None
    code_ref: int = None
    transaction_type: str = ""
    trade_date: str = ""
    start_date: str = ""
    daily_shares: int = None
    leveraged: str = "Yes"
    spot: float = 0.0
    strike_rate: float = 0.0
    ko_rate: float = 0.0
    tenor: str = ""
    frequency: str = ""
    gtd: str = "1m"
    bank_doc: str = ""
    status: str = "active"
    reviewed: int = 0
    locked: int = 0

    def __post_init__(self):
        if self.ref_num:
            self.strike = "{0:,.4f}".format(self.spot * self.strike_rate / 100)
            self.ko = "{0:,.4f}".format(self.spot * self.ko_rate / 100)

            self.ccy_ref = self.db.execute("SELECT ccy_ref FROM tbl_code WHERE ref_num=?",
                                           (self.code_ref, )).fetchone()[0]

            self.ccy_id = self.db.execute("SELECT ccy_id FROM tbl_currency WHERE ref_num=?",
                                           (self.ccy_ref, )).fetchone()[0]

            self.bank_id, self.bank_name = self.db.execute(
                "SELECT bank_id, bank_name FROM tbl_bank_account WHERE ref_num=?;",
                (self.bank_ref,)).fetchone()

            self.stock_name, self.code = self.db.execute("SELECT stock_name, code FROM tbl_code WHERE ref_num=?;",
                                                         (self.code_ref,)).fetchone()

            periods = self.db.execute("SELECT * FROM tbl_stock_contract_period WHERE contract_ref=?;",
                                      (self.ref_num, )).fetchall()

            # Periods and Days
            self.total_periods = len(periods)
            self.received_periods = 0
            self.received_shares = 0

            self.total_days = 0
            self.received_days = 0

            for i, period in enumerate(periods):
                # Determine next period
                if i == 0:
                    self.next_date = self.next_working_day(period['end_date'])

                if period['received']:
                    self.received_periods += 1
                    self.received_shares += _to_int(period['received'])
                    self.received_days += _to_int(period['days'])

                    try:
                        self.next_date = self.next_working_day(periods[i+1]['end_date'])
                    except IndexError:
                        self.next_date = "DONE"


                self.total_days += _to_int(period['days'])
               
                self.end_date = period['end_date']  # The last end_date shall be used by the term sheet

            if self.frequency != "monthly":
                frequencies = {
                    "bi-monthly": 2,
                    "bi-weekly": 2,
                    "weekly": 4,
                }
                self.total_periods = self.total_periods / frequencies[self.frequency]
                self.received_periods = self.received_periods / frequencies[self.frequency]

            self.remaining_periods = self.total_periods - self.received_periods
            self.remaining_days = self.total_days - self.received_days

            self.total_shares = self.total_days*self.daily_shares* 2 if self.leveraged == "Yes" else self.total_days*self.daily_shares
            self.remaining_shares = self.remaining_days*self.daily_shares* 2 if self.leveraged == "Yes" else self.remaining_days*self.daily_shares

    def next_working_day(self, date_):
        dte_date = datetime.strptime(date_, "%Y-%m-%d")
        dte_date += timedelta(days=1)

        holidays = self.db.execute('SELECT holi_date FROM tbl_holiday WHERE ccy_ref=?', (self.ccy_ref, )).fetchall()
        holidays = [i['holi_date'] for i in holidays]

        while (datetime.strftime(dte_date, "%Y-%m-%d") in holidays
                or dte_date.isoweekday() == 6 or dte_date.isoweekday() == 7):
            dte_date += timedelta(days=1)

        return datetime.strftime(dte_date, "%Y-%m-%d")

    def summary(self):
        self.__post_init__()

        #  Stock Name
        if self.gtd == "No":
            stock_name = f"{self.stock_name} No GTD"
        elif self.gtd == "Yes":
            stock_name = f"{self.stock_name} GTD 1m"
        else:
            stock_name = f"{self.stock_name} GTD {self.gtd}"

        #  Shares
        if self.leveraged == "Yes":
            single = "{0:,.0f}".format(self.daily_shares)
            double = "{0:,.0f}".format(self.daily_shares * 2)
            shares = f"{single} / {double}"
        else:
            shares = "{0:,.0f}".format(self.daily_shares)

        #  Dates
        start_date = datetime.strftime(datetime.strptime(self.start_date, "%Y-%m-%d"), "%d-%b-%Y")
        end_date = datetime.strftime(datetime.strptime(self.end_date, "%Y-%m-%d"), "%d-%b-%Y")

        if self.next_date == "DONE":
            next_date = "DONE"
        elif self.status == "KO":
            next_date = "KO"
        else:
            next_date = datetime.strftime(datetime.strptime(self.next_date, "%Y-%m-%d"), "%d-%b-%Y")

        dict_summary = {
            "ref_num": self.ref_num,
            "locked": self.locked,
            "stock_name": stock_name,
            "code": self.code,
            "spot": "{0:,.4f}".format(self.spot),
            "shares": shares,
            "strike": "{0:,.4f}".format(self.spot * self.strike_rate / 100),
            "ko": "{0:,.4f}".format(self.spot * self.ko_rate / 100),
            "start_date": start_date,
            "end_date": end_date,
            "received": (self.received_periods, "20 days"),
            "remaining": (self.remaining_periods, "100 days"),
            "total": (self.total_periods, "120 days"),
            "next_date": next_date,
            "bank_doc": self.bank_doc,
            "reference": self.reference,
            "status": self.status,
        }

        return dict_summary

    def get_schedules(self):
        self.__post_init__()
        self.schedules = []
        sched_refs = self.db.execute("SELECT ref_num FROM tbl_stock_contract_period WHERE contract_ref=?",
                                     (self.ref_num, )).fetchall()
        sched_refs = [i[0] for i in sched_refs]
        for sched_ref in sched_refs:
            period = FixingSchedule(db=self.db)
            period.get(ref_num=sched_ref)
            self.schedules.append(period)

    def as_dict(self):
        self.__post_init__()

        #  Shares
        single = self.daily_shares
        double = single * 2 if self.leveraged == "Yes" else single

        #  Dates
        start_date = self.start_date
        end_date = self.end_date

        if self.next_date == "DONE":
            next_date = "Done"
        elif self.status == "KO":
            next_date = "KO"
        else:
            next_date = self.next_date

        _dict = {
            "ref_num": self.ref_num,
            "transaction_type": self.transaction_type,
            "stock_name": self.stock_name,
            "ccy_id": self.ccy_id,
            "code": self.code,
            "spot": self.spot,
            "single": single,
            "double": double,
            "strike": round(self.spot * self.strike_rate / 100, 4),
            "ko": round(self.spot * self.ko_rate / 100, 4),
            "start_date": start_date,
            "end_date": end_date,
            "received": self.received_periods,
            "remaining": self.remaining_periods,
            "total": self.total_periods,
            "total_days": self.total_days,
            "received_days": self.received_days,
            "remaining_days": self.remaining_days,
            "next_date": next_date,
            "bank_doc": self.bank_doc,
            "reference": self.reference,
        }

        return _dict


@dataclass
class FixingSchedule(Model):
    table_name: str = field(repr=False, default="tbl_stock_contract_period")
    ref_num: int = None
    contract_ref: int = None
    start_date: str = None
    end_date: str = None
    days: any = ""  # TODO: Refactor to int when migration to v1.0 is done
    received: any = ""  # TODO: Refactor to int when migration to v1.0 is done
    gtd: str = ""

    def __post_init__(self):
        # Normalise on save so no new comma-strings (e.g. '24,000' from the edit
        # form) get written to tbl_stock_contract_period. Blank stays "" to
        # preserve the "not received" marker. Reads of legacy data are still
        # guarded by _to_int in StockContract.__post_init__.
        self.days = _normalize_period_value(self.days)
        self.received = _normalize_period_value(self.received)


@dataclass
class TermSheet(Model):
    bank_ref: int = None
    transaction_type: str = None
    status: str = None

    def web(self):
        sql = "SELECT ref_num FROM tbl_stock_contract WHERE bank_ref=? AND transaction_type=? AND status!='inactive'"
        contract_refs = self.db.execute(sql, (self.bank_ref, self.transaction_type)).fetchall()

        term_sheets = []
        for row in contract_refs:
            ts = StockContract(db=self.db)
            ts.get(ref_num=row["ref_num"])
            term_sheets.append(ts.summary())

        return term_sheets


class CreateSchedules:
    def __init__(self, term_sheet, db):
        self.db = db

        contract_ref = term_sheet.ref_num

        self.trade_date = term_sheet.trade_date

        self.code_ref = term_sheet.code_ref
        self.tenor = int(term_sheet.tenor.replace('m', ''))
        self.frequency = term_sheet.frequency

        self.start_date = term_sheet.start_date
        self.end_day, self.end_date = self.__end_date()

        self.gtd = int(term_sheet.gtd.replace("m", "")) if term_sheet.gtd.replace("m", "").isdigit() else 0

        if self.frequency in ("bi-monthly", "bi-weekly"):
            self.gtd *= 2
        elif self.frequency == "weekly":
            self.gtd *= 4

        if self.frequency == "monthly":
            # UNCHANGED behaviour: month-anchored while-loop. Saves each period
            # including the final one (the old `or self.frequency == "monthly"`
            # guard was always true here).
            start_date = self.start_date
            end_date = self.trade_date
            i = 0
            while end_date < self.end_date:
                i += 1
                end_date = self.__next_end_date(end_date, i)
                end_date_on_record = self.check_date(end_date)
                days = Counter(self.db, start_date, end_date, self.code_ref).count
                FixingSchedule(
                    db=self.db, contract_ref=contract_ref, start_date=start_date,
                    end_date=end_date, days=days,
                    gtd="Yes" if i <= self.gtd else "No",
                ).save()
                start_date = self.__next_start_date(end_date_on_record)
        else:
            # bi-weekly / bi-monthly / weekly: fixed grid anchored at start_date,
            # each end rolled forward independently (no cascade), N periods to
            # span the tenor including the final period.
            step = 7 if self.frequency == "weekly" else 14
            anchor = datetime.strptime(str(self.start_date)[:10], "%Y-%m-%d")
            maturity = datetime.strptime(str(self.end_date)[:10], "%Y-%m-%d")
            num_periods = max(1, round((maturity - anchor).days / step))
            start_date = self.start_date
            for i in range(1, num_periods + 1):
                grid_end = str((anchor + timedelta(days=step * i - 1)).date())
                end_date = self.check_date(grid_end)
                days = Counter(self.db, start_date, end_date, self.code_ref).count
                FixingSchedule(
                    db=self.db, contract_ref=contract_ref, start_date=start_date,
                    end_date=end_date, days=days,
                    gtd="Yes" if i <= self.gtd else "No",
                ).save()
                start_date = self.__next_start_date(end_date)

    def __end_date(self):
        year = int(self.trade_date[:4])
        month = int(self.trade_date[5:7])
        end_day = int(self.trade_date[-2:])

        end_year = year
        end_month = month + self.tenor
        if end_month > 12: 
            end_month -= 12            
            end_year += 1

        end_date = str(date(end_year, end_month, end_day))
        end_date = self.check_date(end_date)

        return end_day, end_date

    def __next_end_date(self, previous_end_date, i):
        # monthly only — bi-weekly/weekly is generated inline in __init__ from a
        # fixed start_date grid.
        # Anchor the period-end on the trade month + i, NOT on the previous
        # end date. Deriving the month from previous_end_date skips a whole
        # month whenever an earlier end was pushed forward across a month
        # boundary by check_date (e.g. Feb 29->28 on a Sunday -> Mar 1),
        # producing a single ~40-day period. End-of-month trades hit this
        # routinely. See tests/unit/test_term_sheet_schedule.py.
        trade_year = int(self.trade_date[:4])
        trade_month = int(self.trade_date[5:7])
        total = (trade_month - 1) + i
        end_year = trade_year + total // 12
        end_month = total % 12 + 1

        end_date = None
        day = self.end_day
        while end_date is None:
            try:
                end_date = str(date(end_year, end_month, day))
            except ValueError:
                day -= 1

        return self.check_date(end_date)

    def __next_start_date(self, previous_end_date):
        year = int(previous_end_date[:4])
        day = int(previous_end_date[-2:])
        month = int(previous_end_date[5:7])

        start_date = str(date(year, month, day) + timedelta(days=1))

        return self.check_date(start_date)

    def check_date(self, end_date):
        end_date_on_record = datetime.strptime(end_date, '%Y-%m-%d')

        while True:
            if self.is_holiday(end_date_on_record): 
              end_date_on_record += timedelta(days=1)
            elif end_date_on_record.isoweekday() in (6, 7): 
              end_date_on_record += timedelta(days=1)
            else: 
              break

        return str(end_date_on_record)[:10]

    def is_holiday(self, _date):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            INNER JOIN tbl_code ON tbl_code.ccy_ref = tbl_currency.ref_num
            WHERE tbl_holiday.holi_date=? AND tbl_code.ref_num=?
        """
        if self.db.execute(sql, (str(_date)[:10], self.code_ref)).fetchone()[0]:
            return True
        else:
            return False


class Counter:
    def __init__(self, db, start_date, end_date, code_ref):
        self.db = db
        self.code_ref = code_ref

        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        self.date_list = []
        current_date = start_date
        while end_date>=current_date:
            if self.is_holiday(current_date) or current_date.isoweekday() in (6, 7): 
                pass
            else:
                self.date_list.append(current_date)
            current_date += timedelta(days=1)
        self.count = (len(self.date_list))

    def is_holiday(self, _date):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            INNER JOIN tbl_code ON tbl_code.ccy_ref = tbl_currency.ref_num
            WHERE tbl_holiday.holi_date=? AND tbl_code.ref_num=?
        """
        if self.db.execute(sql, (str(_date)[:10], self.code_ref)).fetchone()[0]:
            return True
        else:
            return False


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

    def is_holiday(_date):
        sql = """
            SELECT COUNT(*) FROM tbl_holiday 
            INNER JOIN tbl_currency ON tbl_holiday.ccy_ref = tbl_currency.ref_num 
            WHERE tbl_holiday.holi_date=? AND tbl_currency.ccy_id=?
        """
        if db.execute(sql, (str(_date)[:10], "HKD")).fetchone()[0]:
            return True
        else:
            return False

    return check_date(_date)
