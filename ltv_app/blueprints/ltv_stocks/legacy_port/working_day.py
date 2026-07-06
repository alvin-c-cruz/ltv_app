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
