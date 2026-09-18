"""Verification: a contract that knocked out inside the report window is still
selected for the LTV Stocks sheet, even though its status has already flipped
to 'KO'.

Regression guard. Selecting on `status = 'active'` alone dropped exactly the
knock-outs the week's report exists to show, because the status flips as soon
as the settlement is recorded -- in practice the same day, not "next week".

Expectations are derived from the database at runtime; nothing is pasted in,
so this carries no client figures and is safe for the public repo.

    .venv/Scripts/python.exe scripts/verify_ko_contracts_in_window.py
"""
import datetime
import os
import sqlite3
import sys

SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SERVER)

from ltv_app.blueprints.ltv_stocks.legacy_port.report_data import week_dates
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records

DB = os.path.join(SERVER, "instance", "LTV Stocks.db")

failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row

    # Anchor on a date the data actually covers: the most recent trade date
    # that has a '-KO)' settlement. Avoids pinning the test to a calendar date.
    row = db.execute(
        "SELECT MAX(trade_date) AS d FROM tbl_transaction "
        "WHERE transaction_type LIKE '%-KO)'"
    ).fetchone()
    if not row or not row["d"]:
        print("SKIP: no knock-out settlements in this database")
        return 0

    report_date = datetime.date.fromisoformat(str(row["d"])[:10])
    dr = week_dates(report_date)
    lo, hi = str(dr[0]), str(dr[-1])
    print("report window: %s -> %s" % (lo, hi))

    # Every (bank, stock) that settled a knock-out inside the window.
    settled = {
        (r["bank_ref"], r["code_ref"])
        for r in db.execute(
            "SELECT DISTINCT bank_ref, code_ref FROM tbl_transaction "
            "WHERE transaction_type LIKE '%-KO)' AND trade_date BETWEEN ? AND ?",
            (lo, hi),
        )
    }
    print("bank/stock pairs with a knock-out in the window: %d" % len(settled))

    banks = [r["ref_num"] for r in db.execute("SELECT ref_num FROM tbl_bank_account")]

    selected, active_only = set(), set()
    for bref in banks:
        for ttype in ("ACCU", "DECU"):
            for r in contract_records(db, bref, ttype, dr[0], dr[-1]):
                selected.add(r["ref_num"])
            for r in contract_records(db, bref, ttype):
                active_only.add(r["ref_num"])

    # 1. Every KO contract whose settlement landed in the window is selected.
    expected_ko = {
        r["ref_num"]
        for r in db.execute("SELECT ref_num, bank_ref, code_ref, status FROM tbl_stock_contract WHERE status = 'KO'")
        if (r["bank_ref"], r["code_ref"]) in settled
    }
    missing = expected_ko - selected
    check(not missing, "all %d KO contracts settled in the window are selected%s"
          % (len(expected_ko), "" if not missing else " (missing %s)" % sorted(missing)))

    # 2. They are genuinely extra -- the active-only selection omitted them.
    check(expected_ko and not (expected_ko & active_only),
          "those %d are absent from the active-only selection (regression is real)" % len(expected_ko))

    # 3. No 'inactive' contract is ever selected.
    inactive = {r["ref_num"] for r in db.execute(
        "SELECT ref_num FROM tbl_stock_contract WHERE status = 'inactive'")}
    check(not (selected & inactive), "no 'inactive' contract is selected")

    # 4. A KO contract with no settlement in the window is NOT selected.
    stale_ko = {
        r["ref_num"]
        for r in db.execute("SELECT ref_num, bank_ref, code_ref FROM tbl_stock_contract WHERE status = 'KO'")
        if (r["bank_ref"], r["code_ref"]) not in settled
    }
    leaked = stale_ko & selected
    check(not leaked, "KO contracts with no settlement in the window stay out (%d such%s)"
          % (len(stale_ko), "" if not leaked else ", leaked %s" % sorted(leaked)))

    # 5. Omitting the dates preserves the old, active-only behaviour.
    check(active_only <= selected and len(active_only) < len(selected) or not expected_ko,
          "the no-date call is still active-only and is a subset of the windowed call")

    print("\nRESULT: %s" % ("ALL PASS" if not failures else "FAIL (%d)" % len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
