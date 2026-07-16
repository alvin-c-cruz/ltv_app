"""Regression harness for the Decumulator/Accumulator period-schedule generator.

Regenerates each golden contract's schedule with CreateSchedules on a throwaway
copy of instance/LTV Stocks.db and diffs it, period-by-period, against the
contract's stored (bank-correct) tbl_stock_contract_period rows. Exit 0 iff all
match. Run: server/.venv/Scripts/python.exe scripts/verify_period_schedule.py
"""
import os, sys, shutil, tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.term_sheet.models import CreateSchedules

GOLDEN = [1449, 1444, 1441]
SRC = os.path.join(SERVER, "instance", "LTV Stocks.db")


def _periods(db, ref):
    return [(str(r["start_date"])[:10], str(r["end_date"])[:10], r["days"])
            for r in db.execute(
                "SELECT start_date, end_date, days FROM tbl_stock_contract_period "
                "WHERE contract_ref=? ORDER BY start_date", (ref,)).fetchall()]


def _contract(db, ref):
    r = db.execute(
        "SELECT ref_num, trade_date, start_date, code_ref, tenor, frequency, gtd "
        "FROM tbl_stock_contract WHERE ref_num=?", (ref,)).fetchone()
    if r is None:
        return None
    return SimpleNamespace(
        ref_num=r["ref_num"], trade_date=str(r["trade_date"])[:10],
        start_date=str(r["start_date"])[:10], code_ref=r["code_ref"],
        tenor=r["tenor"], frequency=r["frequency"], gtd=str(r["gtd"]))


def _open(path):
    app = create_app()
    app.config["DATABASE"] = path
    ctx = app.app_context()
    ctx.push()
    return ctx, get_db()


def main():
    failures = 0
    for ref in GOLDEN:
        ctx0, db0 = _open(SRC)
        ts = _contract(db0, ref)
        expected = _periods(db0, ref) if ts else []
        db0.close()
        ctx0.pop()
        if not ts or not expected:
            print(f"  #{ref}: SKIP (contract or stored schedule not found)")
            failures += 1
            continue

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        shutil.copy(SRC, tmp)
        try:
            ctx, db = _open(tmp)
            try:
                db.execute("DELETE FROM tbl_stock_contract_period WHERE contract_ref=?", (ref,))
                db.commit()
                CreateSchedules(ts, db)
                actual = _periods(db, ref)
            finally:
                # get_db() never registers a teardown_appcontext/close_db, so
                # g.db would otherwise stay open; close explicitly (even if
                # the body above raised) or os.unlink(tmp) below fails with
                # WinError 32 (file still locked) on Windows.
                db.close()
                ctx.pop()
        finally:
            os.unlink(tmp)

        if actual == expected:
            print(f"  #{ref} {ts.frequency}: PASS ({len(expected)} periods)")
        else:
            failures += 1
            print(f"  #{ref} {ts.frequency}: FAIL  expected {len(expected)} periods, got {len(actual)}")
            for i in range(max(len(expected), len(actual))):
                e = expected[i] if i < len(expected) else None
                a = actual[i] if i < len(actual) else None
                if e != a:
                    print(f"      P{i+1}: expected {e}  got {a}")
                    break

    print("RESULT:", "ALL PASS" if failures == 0 else f"{failures} contract(s) FAIL")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
