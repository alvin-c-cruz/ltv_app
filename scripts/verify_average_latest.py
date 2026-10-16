"""Regression harness: the /ltv-stocks/ average is the latest running average as of the
report date -- every row traded up to that date counts, whenever it settles.

The legacy port of trades_done_average stopped at the first row settling in a LATER
month than the report date. On a month-end report, a buy traded that day but settling
next month therefore moved the row's narrative total and not the Ave. Price beside it.
Alvin, 2026-09-30: "/ltv-stocks should always show the most updated average. We have the
quantity affected here so we need the average be affected too." See BUGS.md.

Every case finds its own fixture at runtime -- each buy, on an account whose
transaction_basis is value_date, whose value_date falls in a later month than its
trade_date -- and compares positions_calc._average() as of that trade date with the
running average the bank ledger page and /trades/average_price show
(TradesDoneAverage -> transactions.models.accumulate_position), an independent code
path. No balances, prices or narratives are held in this file or printed by it: the
repository is public.

All queries are read-only (SELECT-only); this script never mutates the database.

Run: python scripts/verify_average_latest.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import _average
from ltv_app.blueprints.transactions.extensions.trades_done_average import TradesDoneAverage

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")


def _case(label, ok):
    # Deliberately never interpolates a balance, price or average.
    print(f"  {label}: {'PASS' if ok else 'FAIL'}")
    return ok


def _cross_month_buys(db):
    """(bank_id, code, trade_date) of every buy that settles in a later month than it trades,
    on a value_date-basis account -- the rows the month-end break used to drop."""
    return db.execute(
        "SELECT DISTINCT b.bank_id, s.code, substr(t.trade_date, 1, 10) AS trade_date "
        "FROM tbl_transaction t "
        "JOIN tbl_code s ON s.ref_num = t.code_ref "
        "JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "WHERE b.transaction_basis = 'value_date' AND t.quantity > 0 "
        "AND substr(t.value_date, 1, 7) > substr(t.trade_date, 1, 7)"
    ).fetchall()


def main():
    app = create_app()
    app.config["DATABASE"] = DB_PATH
    with app.app_context():
        db = get_db()
        fixtures = _cross_month_buys(db)
        checked = matched = 0
        for f in fixtures:
            ledger = TradesDoneAverage(db, f["trade_date"], f["code"], f["bank_id"], include_transfers=True)
            if ledger.balance <= 0:      # flat or short positions: the two paths' fallbacks differ by design
                continue
            checked += 1
            report = _average(db, f["bank_id"], f["code"], date.fromisoformat(f["trade_date"]))
            if report is not None and abs(report - ledger.average) < 1e-9:
                matched += 1
        ok = _case("A fixtures found (buys settling in a later month)", checked > 0)
        ok &= _case(f"B report average == ledger running average on {checked} such report dates",
                    checked > 0 and matched == checked)
        if checked and matched != checked:
            print(f"     {checked - matched} of {checked} differ")
    print("RESULT: ALL PASS" if ok else "RESULT: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
