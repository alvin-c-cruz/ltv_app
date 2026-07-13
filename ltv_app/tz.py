from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PH_TZ = ZoneInfo("Asia/Manila")


def ph_now() -> datetime:
    return datetime.now(PH_TZ)


def ph_today() -> date:
    return ph_now().date()


def add_business_days(start: date, days: int) -> date:
    """Add N business days to start, skipping weekends."""
    result = start
    added = 0
    while added < days:
        result += timedelta(days=1)
        if result.weekday() < 5:  # Mon–Fri
            added += 1
    return result
