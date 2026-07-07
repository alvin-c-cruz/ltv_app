from datetime import date, timedelta


class WorkingDay:
    """Holiday-aware working-day helper for one currency, backed by tbl_holiday.
    Ports localhost/modules/working_day.py against get_db()-style connections."""

    def __init__(self, db, ccy_id):
        rows = db.execute(
            "SELECT h.holi_date FROM tbl_holiday h "
            "INNER JOIN tbl_currency c ON c.ref_num = h.ccy_ref "
            "WHERE c.ccy_id = ?", (ccy_id,)
        ).fetchall()
        self._holidays = {str(r[0])[:10] for r in rows}

    def is_holiday(self, d: date) -> bool:
        return d.weekday() >= 5 or d.isoformat() in self._holidays

    def next_day(self, d: date) -> date:
        d = d + timedelta(days=1)
        while self.is_holiday(d):
            d = d + timedelta(days=1)
        return d

    def previous_day(self, d: date) -> date:
        d = d - timedelta(days=1)
        while self.is_holiday(d):
            d = d - timedelta(days=1)
        return d

    def count_days(self, start: date, end: date) -> int:
        """Inclusive count of weekday, non-holiday dates from start to end."""
        n, d = 0, start
        while d <= end:
            if not self.is_holiday(d):
                n += 1
            d = d + timedelta(days=1)
        return n


def position_start_date(report_date: date, hkd_wd: 'WorkingDay') -> date:
    """Port of LTV_Stocks.__init__'s self.start_date (ltv_stocks2.py ~121-123):
    walk back via the **HKD** working day (regardless of the sheet's own currency)
    until landing on a Monday. This is also the balance-snapshot date used by
    Gather_Info/stock_position (ltv_stocks2.py:33), not just a header label."""
    d = hkd_wd.previous_day(report_date)
    while d.isoweekday() != 1:
        d = hkd_wd.previous_day(d)
    return d
