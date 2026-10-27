"""Regression harness for ltv_stocks/legacy_port/positions_calc.py.

Pins the four narrative/average bugs fixed in this codebase's 2026-07 session,
so a future change to _average, _transactions_narrative, or
inject_accu_only_positions can't silently regress them:

  A  the narrative's running total is the true ending balance as of the report
     date, not the beginning-of-week snapshot printed beside it;
  B  a Transfer-Out names the account the shares went to, and a position
     closed out to zero shows the average it was carried at, not a bare 0;
  C  an ACCU-only placeholder row shows the real, charge-inclusive average
     cost, not the contract's strike price;
  D  a genuine zero-cost average on a nonzero balance stays 0.0 rather than
     being read as "no average" (None).

Every case finds its own fixture at runtime and derives what to expect from the
database, so this file holds no holdings, prices or trade narratives -- the
repository it lives in is public. Until 2026-10 it pinned literal figures read
off the live ledger; see BUGS.md 2026-09-06. The expected average comes from
_carried_average(), the plain definition of average cost (total cost of the
buys over the shares bought), which is exact for the shapes these fixtures are
chosen from and shares no code with _moving_average_engine. A and C also sweep
every sheet of every Friday report of 2026, so a per-fixture patch cannot
satisfy them.

All queries here are read-only (SELECT-only); this script never mutates the
database.

Run: server/.venv/Scripts/python.exe scripts/verify_positions_calc.py
"""
import math
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import (
    _average, _transactions_narrative, position_records,
)
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records
from ltv_app.blueprints.ltv_stocks.legacy_port.report_data import inject_accu_only_positions
from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import (
    WorkingDay, position_start_date,
)

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")

# The same roster the /ltv-stocks/ report is generated for (ltv_stocks/views.py).
BANK_IDS = ["DBPe", "DBPL", "SHK", "SHK2", "MST1", "MST2", "MSPL", "NSG"]
CCYS = ("HKD", "SGD")

_CHARGES = "t.brokerage + t.commission + t.foreign_charge + t.stamp_duty + t.misc"


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
    # Deliberately prints neither value: a failure here should not put holdings,
    # prices or narratives into a terminal or a CI log.
    print(f"  {label}: FAIL")
    return False


def _close(a, b):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)


def _bank_refs(db):
    return {
        b: db.execute(
            "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (b,)
        ).fetchone()["ref_num"]
        for b in BANK_IDS
    }


def _report_fridays(db):
    """Every Friday of 2026 up to the newest trade in the database."""
    last = date.fromisoformat(
        str(db.execute("SELECT MAX(trade_date) FROM tbl_transaction").fetchone()[0])[:10])
    d = date(2026, 1, 2)
    out = []
    while d <= last:
        out.append(d)
        d += timedelta(days=7)
    return out


def _as_of(report_date, hkd_wd):
    """The date the sheet's "AS OF" header names, and the date the beginning
    balance is snapshotted on."""
    return hkd_wd.previous_day(position_start_date(report_date, hkd_wd))


def _balance(db, bank_ref, code_ref, on_date):
    return db.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM tbl_transaction "
        "WHERE bank_ref = ? AND code_ref = ? AND trade_date <= ?",
        (bank_ref, code_ref, on_date.isoformat())
    ).fetchone()[0]


def _expected_ending(balance):
    """How _transactions_narrative spells its running total."""
    return "= " + "{:,.0f}".format(balance)


def _ledger(db, bank_id, code, as_of):
    """The rows _average reads for one (bank, code): traded up to as_of, in the
    bank's transaction_basis order, then transaction-type priority."""
    basis = db.execute(
        "SELECT transaction_basis FROM tbl_bank_account WHERE bank_id = ?", (bank_id,)
    ).fetchone()[0]
    return db.execute(
        f"SELECT t.quantity, t.quantity * t.price + {_CHARGES} AS amount "
        "FROM tbl_transaction t "
        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
        "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type "
        "WHERE s.code = ? AND b.bank_id = ? AND t.trade_date <= ? "
        f"ORDER BY t.{basis}, tt.priority, t.ref_num",
        (code, bank_id, as_of.isoformat())
    ).fetchall()


def _carried_average(db, bank_id, code, as_of):
    """(balance, average) for one (bank, code) as of as_of, where average is the
    total cost of the buys (charges included) over the shares they bought, taken
    over the run the position is carried from: since it was last flat or, when
    it is flat now, the run that ended there. A sale leaves the average where it
    was, so this is exact whenever every buy in that run comes before every sale
    and the position never goes short. Otherwise average is None: the shape is
    outside what this oracle can price, and the caller looks for another
    fixture."""
    rows = _ledger(db, bank_id, code, as_of)
    runs, run, balance = [], [], 0
    for r in rows:
        run.append(r)
        balance += r["quantity"]
        if balance == 0:
            runs.append(run)
            run = []
    run = run or (runs[-1] if runs else [])

    held, shares, cost, sold = 0, 0, 0.0, False
    for r in run:
        q = r["quantity"]
        if q > 0:
            if sold:
                return balance, None
            shares += q
            cost += r["amount"]
        else:
            sold = True
        held += q
        if held < 0:
            return balance, None
    return balance, (cost / shares if shares else None)


def _sheet(db, bank_ref, bank_id, ccy, report_date, hkd_wd):
    """One bank/currency sheet: the balance-derived rows, the ACCU contracts, and
    the rows with the ACCU-only placeholders added, as
    excel_writer.build_workbook assembles them."""
    accu = [r for r in contract_records(db, bank_ref, "ACCU") if r["ccy_id"] == ccy]
    positions = position_records(db, bank_ref, bank_id, ccy, report_date, hkd_wd=hkd_wd)
    rows = inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date)
    return positions, accu, rows


def main():
    ctx, db = _open()
    try:
        ok = True
        refs = _bank_refs(db)
        hkd_wd = WorkingDay(db, "HKD")
        report_dates = _report_fridays(db)

        sheets = []
        for report_date in report_dates:
            for bank_id in BANK_IDS:
                for ccy in CCYS:
                    positions, accu, rows = _sheet(db, refs[bank_id], bank_id, ccy,
                                                   report_date, hkd_wd)
                    sheets.append((report_date, bank_id, ccy, positions, accu, rows))

        # --- Case A: the narrative's running total is the TRUE ending balance as
        # of the report date. It used to print the beginning-of-week snapshot,
        # the figure in the balance column beside it, so a week that moved the
        # holding showed a total its own trades did not add up to.
        moved = None
        wrong_total = 0
        for report_date, bank_id, ccy, positions, accu, rows in sheets:
            for code, rec in rows.items():
                if not rec["transactions"]:
                    continue
                ending = _balance(db, refs[bank_id], rec["code_ref"], report_date)
                if not rec["transactions"].endswith(_expected_ending(ending)):
                    wrong_total += 1
                if ending != rec["balance"]:
                    moved = (rec, ending)
        ok &= _case("A0 a week that moved a holding exists to test", moved is not None, True)
        if moved:
            rec, ending = moved
            ok &= _case("A1 its narrative total is the ending balance, not the AS-OF one",
                        rec["transactions"].endswith(_expected_ending(ending))
                        and not rec["transactions"].endswith(_expected_ending(rec["balance"])),
                        True)
        ok &= _case("A2 narratives on 2026 sheets whose total is not the ending balance",
                    wrong_total, 0)

        # --- Case B1: a Transfer-Out names the account the shares went to.
        out_leg = db.execute(
            "SELECT t.bank_ref, t.code_ref, t.trade_date, b.bank_name "
            "FROM tbl_transaction t "
            "INNER JOIN tbl_bank_account b ON b.ref_num = t.counter_bank_ref "
            "WHERE t.transaction_type = 'Transfer-Out' AND b.bank_name IS NOT NULL "
            "ORDER BY t.trade_date DESC, t.ref_num DESC LIMIT 1"
        ).fetchone()
        ok &= _case("B1a a Transfer-Out to a known account exists to test",
                    out_leg is not None, True)
        if out_leg:
            narrative = _transactions_narrative(
                db, out_leg["bank_ref"], out_leg["code_ref"],
                date.fromisoformat(str(out_leg["trade_date"])[:10]))
            ok &= _case("B1b Transfer-Out narrative names the destination account",
                        f"Transfer-Out (to {out_leg['bank_name']})" in narrative, True)

        # --- Case B2: a position closed out to exactly zero has no cost/balance
        # ratio (0/0). _average shows the last average on record -- what the
        # position was carried at -- instead of a bare 0, which reads as "no
        # cost basis". _average returns a plain evaluated float.
        closed = None
        seen = set()
        for r in db.execute(
                "SELECT b.bank_id, s.code, t.trade_date FROM tbl_transaction t "
                "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
                "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
                "WHERE t.quantity < 0 ORDER BY t.trade_date DESC, t.ref_num DESC"):
            key = (r["bank_id"], r["code"], date.fromisoformat(str(r["trade_date"])[:10]))
            if key in seen:
                continue
            seen.add(key)
            balance, average = _carried_average(db, *key)
            if balance == 0 and average:
                closed = (key, average)
                break
        ok &= _case("B2a a position closed out to zero exists to test", closed is not None, True)
        if closed:
            key, average = closed
            ok &= _case("B2b zero-balance _average is the average it was carried at",
                        _close(_average(db, *key), average), True)

        # --- Case C: an ACCU contract whose code has no balance-derived row gets
        # a placeholder row from inject_accu_only_positions. Its average is the
        # real, charge-inclusive average cost; it used to be the contract's
        # strike price always.
        #
        # C1-C2 take the shape the bug was found on: a code the account opened
        # during the reported week by accumulator buys, handed to
        # inject_accu_only_positions with no balance-derived row for it (what
        # position_records returned for such a code until 2026-09-06). Picked
        # where the charges make the average differ from the strike, so the old
        # code fails it.
        opened = None
        for report_date, bank_id, ccy, positions, accu, rows in reversed(sheets):
            for contract in accu:
                rec = positions.get(contract["code"])
                if rec is None or rec["balance"] != 0 \
                        or "Buy (Accu)" not in (rec["transactions"] or ""):
                    continue
                balance, average = _carried_average(db, bank_id, contract["code"], report_date)
                if balance > 0 and average is not None \
                        and not _close(average, contract["strike"]):
                    opened = (report_date, bank_id, contract, balance, average)
                    break
            if opened:
                break
        ok &= _case("C0 an ACCU code opened in its report week exists to test",
                    opened is not None, True)
        if opened:
            report_date, bank_id, contract, balance, average = opened
            placeholder = inject_accu_only_positions(
                {}, [contract], db, refs[bank_id], bank_id, report_date
            ).get(contract["code"])
            ok &= _case("C1 placeholder average is the charge-inclusive average",
                        _close(placeholder["average"] if placeholder else None, average), True)
            ok &= _case("C2 placeholder narrative is the week's accumulator buys",
                        placeholder is not None
                        and "Buy (Accu)" in (placeholder["transactions"] or "")
                        and placeholder["transactions"].endswith(_expected_ending(balance)),
                        True)

        # C3-C4 (structural): every placeholder actually written to a 2026 sheet
        # carries the real average wherever _carried_average can price it, and
        # at least one of those differs from its strike -- or C3 could not tell
        # the fix from the bug.
        wrong_average = 0
        off_strike = 0
        for report_date, bank_id, ccy, positions, accu, rows in sheets:
            strikes = {r["code"]: r["strike"] for r in accu}
            for code, rec in rows.items():
                if code in positions or code not in strikes:
                    continue
                balance, average = _carried_average(db, bank_id, code, report_date)
                if average is None:
                    continue
                if not _close(rec["average"], average):
                    wrong_average += 1
                if not _close(average, strikes[code]):
                    off_strike += 1
        ok &= _case("C3 placeholders on 2026 sheets without the real average", wrong_average, 0)
        ok &= _case("C4 a placeholder whose average differs from its strike exists",
                    off_strike > 0, True)

        # --- Case D: a genuine zero-cost average on a nonzero balance -- a
        # position opened only by shares that cost nothing, such as a bonus
        # issue booked at price 0 -- must stay a real average (0.0), not be
        # reclassified as "no average" (None), which would wrongly fall back to
        # a strike-price placeholder in inject_accu_only_positions.
        free = None
        for r in db.execute(
                "SELECT b.bank_id, s.code, t.trade_date FROM tbl_transaction t "
                "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
                "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
                f"WHERE t.quantity > 0 AND t.price = 0 AND {_CHARGES} = 0 "
                "ORDER BY t.trade_date DESC, t.ref_num DESC"):
            key = (r["bank_id"], r["code"], date.fromisoformat(str(r["trade_date"])[:10]))
            balance, average = _carried_average(db, *key)
            if balance > 0 and average == 0:
                free = key
                break
        ok &= _case("D0 a position opened at zero cost exists to test", free is not None, True)
        if free:
            average = _average(db, *free)
            ok &= _case("D1 zero-cost _average is 0.0, not None",
                        average is not None and average == 0, True)
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
