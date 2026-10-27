"""Verification that a knocked-out contract is on the LTV Stocks report only in
the window that holds its own knock-out.

contract_records() keeps a status-'KO' contract on its block when its knock-out
settled inside the report's 10-day window (BUGS.md 2026-09-11). The settlement
rows carry no contract_ref, so it matched any '-KO)' row on the same bank and
stock -- another contract's knock-out, an ACCU's for a DECU, or one from before
the contract existed all put it back on the report. Regenerating a past report
showed contracts that knocked out months later, and verify_ko_offsets_shared /
verify_status_grid failed on the extra row.

record_fixings writes a knock-out with the contract's strike as price and its KO
price as ko, so the settlement is the contract's own when those match, it is of
the contract's own type, and it is on or after the contract's start. A row with
no ko (none since 2022; the trade form never writes one) is matched on type and
start date alone, so a hand-entered knock-out cannot drop its contract.

  A  a contract stays off a report whose window holds only another contract's
     knock-out on the same bank and stock;
  B  every KO contract is on the report whose window holds its own knock-out
     (the 2026-09-11 fix, kept);
  C  over every 2026 Friday report, no KO contract is on one whose window does
     not hold its own knock-out;
  D  on a temp copy with the contract's own ko blanked, the fallback keeps it on
     its own report and off one from before it started.

Fixtures are found at runtime; nothing here names a contract, stock or price,
and a failure prints neither. A-C only read; D writes to a throwaway copy.

Run: server/.venv/Scripts/python.exe scripts/verify_ko_membership.py
"""
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.report_data import week_dates
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")
KO_TYPE = {"ACCU": "Buy (Accu-KO)", "DECU": "Sell (Decu-KO)"}


def _case(label, actual, expected):
    if actual == expected:
        print(f"  {label}: PASS")
        return True
    print(f"  {label}: FAIL")
    return False


def _friday(d):
    """The Friday report whose window ends the week d falls in (a weekend day
    goes to the Friday after)."""
    return d + timedelta(days=(5 - d.isoweekday()) % 7)


def _d(value):
    return date.fromisoformat(str(value)[:10])


def _ko_contracts(db):
    return db.execute(
        "SELECT ref_num, bank_ref, code_ref, transaction_type, start_date, "
        "ROUND(strike_rate*spot/100, 4) AS strike, ROUND(ko_rate*spot/100, 4) AS ko "
        "FROM tbl_stock_contract WHERE status = 'KO' ORDER BY start_date DESC, ref_num DESC"
    ).fetchall()


def _settlements(db, c):
    """Every knock-out row of the contract's own type on its bank and stock,
    each flagged whether it is the contract's own: its strike and KO price, on or
    after its start."""
    rows = db.execute(
        "SELECT ref_num, trade_date, price, ko FROM tbl_transaction "
        "WHERE bank_ref = ? AND code_ref = ? AND transaction_type = ? ORDER BY trade_date",
        (c["bank_ref"], c["code_ref"], KO_TYPE[c["transaction_type"]])).fetchall()
    out = []
    for r in rows:
        own = (str(r["trade_date"])[:10] >= str(c["start_date"])[:10]
               and r["price"] is not None and r["ko"] is not None
               and abs(r["price"] - c["strike"]) < 1e-6 and abs(r["ko"] - c["ko"]) < 1e-6)
        out.append((r, own))
    return out


def _on_report(db, c, report_date):
    window = week_dates(report_date)
    return any(r["ref_num"] == c["ref_num"]
               for r in contract_records(db, c["bank_ref"], c["transaction_type"],
                                         window[0], window[-1]))


def _in_window(day, report_date):
    window = week_dates(report_date)
    return window[0] <= day <= window[-1]


def main():
    app = create_app()
    app.config["DATABASE"] = DB_PATH
    ctx = app.app_context()
    ctx.push()
    ok = True
    try:
        db = get_db()
        contracts = _ko_contracts(db)
        own_day = {}
        foreign = None
        before_start = None
        for c in contracts:
            rows = _settlements(db, c)
            mine = [_d(r["trade_date"]) for r, own in rows if own]
            if mine:
                own_day[c["ref_num"]] = mine[0]
            for r, own in reversed(rows):
                day = _d(r["trade_date"])
                if own or not mine or _in_window(mine[0], _friday(day)):
                    continue
                if foreign is None:
                    foreign = (c, _friday(day))
                if before_start is None and day < _d(c["start_date"]):
                    before_start = (c, _friday(day), r["ref_num"])
        ok &= _case("B0 status-KO contracts exist to test", len(contracts) > 0, True)
        ok &= _case("B1 each has its own knock-out settlement", len(own_day), len(contracts))

        # --- A: another contract's knock-out on the same bank and stock.
        ok &= _case("A0 a KO contract with another knock-out on its stock exists",
                    foreign is not None, True)
        if foreign:
            c, report_date = foreign
            ok &= _case("A1 it is not on the report of that other knock-out",
                        _on_report(db, c, report_date), False)

        # --- B: its own knock-out still puts it on the report.
        missing = sum(1 for c in contracts if c["ref_num"] in own_day
                      and not _on_report(db, c, _friday(own_day[c["ref_num"]])))
        ok &= _case("B2 KO contracts missing from the report of their own knock-out",
                    missing, 0)

        # --- C (structural): every 2026 Friday report, every bank and product
        # that has a KO contract.
        last = _d(db.execute("SELECT MAX(trade_date) FROM tbl_transaction").fetchone()[0])
        blocks = {(c["bank_ref"], c["transaction_type"]) for c in contracts}
        by_ref = {c["ref_num"]: c for c in contracts}
        stray = 0
        report_date = date(2026, 1, 2)
        while report_date <= last:
            window = week_dates(report_date)
            for bank_ref, product in blocks:
                for r in contract_records(db, bank_ref, product, window[0], window[-1]):
                    if r["ref_num"] in by_ref and not (
                            r["ref_num"] in own_day
                            and window[0] <= own_day[r["ref_num"]] <= window[-1]):
                        stray += 1
            report_date += timedelta(days=7)
        ok &= _case("C KO contracts on a 2026 report without their own knock-out", stray, 0)
    finally:
        ctx.pop()

    # --- D: the fallback for a knock-out row with no ko, on a throwaway copy.
    ok &= _case("D0 a KO contract with an earlier knock-out on its stock exists",
                before_start is not None, True)
    if before_start:
        c, early_report, _ = before_start
        own = own_day[c["ref_num"]]
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        shutil.copy(DB_PATH, tmp)
        conn = sqlite3.connect(tmp)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "UPDATE tbl_transaction SET ko = NULL WHERE bank_ref = ? AND code_ref = ? "
                "AND transaction_type = ? AND trade_date = ?",
                (c["bank_ref"], c["code_ref"], KO_TYPE[c["transaction_type"]], own.isoformat()))
            conn.commit()
            ok &= _case("D1 with no ko on its row, still on its own report",
                        _on_report(conn, c, _friday(own)), True)
            ok &= _case("D2 and still off a report from before it started",
                        _on_report(conn, c, early_report), False)
        finally:
            conn.close()
            os.unlink(tmp)

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
