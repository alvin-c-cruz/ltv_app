"""Regression harness for ltv_stocks/legacy_port/positions_calc.py.

Pins known-good output (captured against the real instance/LTV Stocks.db) for
the four narrative/average bugs fixed in this codebase's 2026-07 session, so
a future change to _average, _transactions_narrative, or
_inject_accu_only_positions can't silently regress them. All functions here
are read-only (SELECT-only) — this script never mutates the database.

Run: server/.venv/Scripts/python.exe scripts/verify_positions_calc.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import (
    _average, _transactions_narrative, position_records,
)
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import _inject_accu_only_positions

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")
REPORT_DATE = date(2026, 7, 10)


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

        # Case A: true ending balance in the narrative (was the stale
        # beginning-of-week snapshot, 99,550).
        ok &= _case(
            "A _transactions_narrative 9988@DBPe",
            _transactions_narrative(db, 5, 52, REPORT_DATE),
            "(7/6) Buy (Accu) 3,200 @ 133.8612 + (7/10) Buy (Accu) 5,400 @ 145.7204 = 108,150",
        )

        # Case B1: Transfer-Out destination label.
        ok &= _case(
            "B1 _transactions_narrative 2196@DBPe",
            _transactions_narrative(db, 5, 83, REPORT_DATE),
            "(7/6) Transfer-Out (to Sun Hung Kai Account No. 2) 35,000 @ 19.1237 = 0",
        )

        # Case B2: zero-balance -> last-average-on-record (was bare 0).
        ok &= _case(
            "B2 _average 2196@DBPe (zero balance)",
            _average(db, "DBPe", "2196", REPORT_DATE),
            "=669330.0/35000",
        )

        # Case C: ACCU-only placeholder uses the real charge-inclusive average
        # (was always the contract's strike price, 15.4454).
        accu = [r for r in contract_records(db, 5, "ACCU")
                if r["ccy_id"] == "HKD" and r["code"] == "3993"]
        positions = position_records(db, 5, "DBPe", "HKD", REPORT_DATE)
        injected = _inject_accu_only_positions(positions, accu, db, 5, "DBPe", REPORT_DATE)
        rec = injected.get("3993")
        ok &= _case("C average 3993@DBPe (ACCU-only)",
                    rec["average"] if rec else None, "=602993.6/39000")
        ok &= _case("C transactions 3993@DBPe (ACCU-only)",
                    rec["transactions"] if rec else None,
                    "(7/7) Buy (Accu) 39,000 @ 15.4454 = 39,000")
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
