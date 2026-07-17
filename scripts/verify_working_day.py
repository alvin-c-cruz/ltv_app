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
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
