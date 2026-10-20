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
    """Port of LTV_Stocks.__init__'s self.start_date (ltv_stocks2.py ~121-123): the
    Monday of report_date's own week. The AS-OF / beginning-balance date is
    `hkd_wd.previous_day()` of it, which the callers take -- the last HKD working
    day before the week opens.

    BUG FIX (diverges from legacy, 2026-10-20): the legacy walked back HKD working
    days until it landed on a Monday. A holiday Monday is never landed on, so a
    report in a week that opens on one (Mon 2026-10-19, Chung Yeung observed;
    Easter Monday 2026-04-06) went back to the previous week's Monday: the
    20 Oct report showed balances AS OF 9 Oct, and the 12-16 Oct trades were in
    neither those balances nor the narrative, which starts at the calendar
    Monday. The calendar Monday is the same day the walk-back reached in every
    other week, including the earlier fix for a report dated a working Monday.
    `hkd_wd` is no longer needed here; the parameter stays for the callers."""
    return report_date - timedelta(days=report_date.isoweekday() - 1)
