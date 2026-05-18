from datetime import date, datetime
from zoneinfo import ZoneInfo

PH_TZ = ZoneInfo("Asia/Manila")


def ph_now() -> datetime:
    return datetime.now(PH_TZ)


def ph_today() -> date:
    return ph_now().date()
