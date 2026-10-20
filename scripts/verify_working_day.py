"""Regression harness for legacy_port/working_day.py's position_start_date.

Pins the Monday-bug fix (report_date itself a non-holiday Monday must resolve
to itself, not the prior week's Monday) against the real instance/LTV
Stocks.db. Read-only -- never mutates the database.

Run: server/.venv/Scripts/python.exe scripts/verify_working_day.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import WorkingDay, position_start_date

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")


def _open():
    app = create_app()
    app.config["DATABASE"] = DB_PATH
    ctx = app.app_context()
    ctx.push()
    return ctx, get_db()


def _case(label, actual, expected):
    if actual == expected:
        print(f"  {label}: PASS")
        return True
    print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")
    return False


def main():
    ctx, db = _open()
    try:
        ok = True
        hkd_wd = WorkingDay(db, "HKD")

        # Case A (the bug): report_date is itself a non-holiday Monday ->
        # must resolve to itself, not the previous week's Monday.
        ok &= _case(
            "A position_start_date(Mon 2026-07-20)",
            position_start_date(date(2026, 7, 20), hkd_wd),
            date(2026, 7, 20),
        )
        ok &= _case(
            "A2 previous_day(start_date) = AS-OF/beginning_date",
            hkd_wd.previous_day(position_start_date(date(2026, 7, 20), hkd_wd)),
            date(2026, 7, 17),
        )

        # Case B (unaffected): a Friday report_date already resolves to that
        # same week's Monday -- must be unchanged by the fix.
        ok &= _case(
            "B position_start_date(Fri 2026-07-10)",
            position_start_date(date(2026, 7, 10), hkd_wd),
            date(2026, 7, 6),
        )

        # Case C (unaffected): a non-Monday, non-Friday weekday (Wednesday)
        # still walks back to that same week's Monday.
        ok &= _case(
            "C position_start_date(Wed 2026-07-08)",
            position_start_date(date(2026, 7, 8), hkd_wd),
            date(2026, 7, 6),
        )

        # Case D (holiday Monday): Mon 2026-10-19 is an HKD holiday (Chung Yeung
        # observed). A Tuesday report must still start that week, AS OF the Friday
        # before it -- not walk past the holiday into the previous week's Monday.
        ok &= _case(
            "D position_start_date(Tue 2026-10-20)",
            position_start_date(date(2026, 10, 20), hkd_wd),
            date(2026, 10, 19),
        )
        ok &= _case(
            "D2 previous_day(start_date) = AS-OF/beginning_date",
            hkd_wd.previous_day(position_start_date(date(2026, 10, 20), hkd_wd)),
            date(2026, 10, 16),
        )

        # Case E: a report dated the holiday Monday itself.
        ok &= _case(
            "E position_start_date(Mon 2026-10-19, holiday)",
            position_start_date(date(2026, 10, 19), hkd_wd),
            date(2026, 10, 19),
        )

        # Case F: Easter 2026 -- Good Friday 3 Apr, Sat 4 Apr, Mon 6 and Tue 7 Apr
        # are all HKD holidays. A Wednesday report starts Mon 6 Apr, AS OF Thu 2 Apr.
        ok &= _case(
            "F previous_day(position_start_date(Wed 2026-04-08))",
            hkd_wd.previous_day(position_start_date(date(2026, 4, 8), hkd_wd)),
            date(2026, 4, 2),
        )
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
