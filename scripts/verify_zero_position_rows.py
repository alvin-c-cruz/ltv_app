"""Regression harness: a (bank, code) that starts the report week flat must
still get a position row when it trades during that week.

`position_records` snapshots the beginning balance as of `beginning_date` (the
previous week's Friday, the date the sheet's "AS OF" header names) and used to
select which codes to emit with that same figure -- `HAVING SUM(quantity) != 0`.
A code that was flat on that Friday therefore got no row at all, so the week's
trades in it had nowhere to print: shares arrived in the account and were
invisible in a client-facing document. Found 2026-09-04, reported after a
transfer between two accounts showed as leaving one and arriving in none (see
server/BUGS.md).

Emission is now driven by the narrative window instead: a code is emitted when
it held a non-zero balance on the AS-OF date *or* traded during the reported
week. Such a row carries a zero beginning balance -- which is the truth, and is
already how `inject_accu_only_positions` renders an ACCU-only code.

Every case finds its own fixture at runtime and derives what to expect from the
database, so this file holds no account balances, prices or trade narratives --
the repository it lives in is public. `_flat_start_cases()` locates the shape
the bug was about; A and B pin a transfer's two legs, C pins the same shape
arising from an ordinary purchase, and D and E are structural: D asserts the
property over every bank/currency sheet across a year of report dates, so it
cannot be satisfied by special-casing transfers, and E asserts the fix does not
emit rows with nothing in them.

All queries here are read-only (SELECT-only); this script never mutates the
database.

Run: server/.venv/Scripts/python.exe scripts/verify_zero_position_rows.py
"""
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import position_records
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records
from ltv_app.blueprints.ltv_stocks.legacy_port.report_data import inject_accu_only_positions
from ltv_app.blueprints.ltv_stocks.legacy_port.working_day import (
    WorkingDay, position_start_date,
)

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")

# The same roster the /ltv-stocks/ report is generated for (ltv_stocks/views.py).
BANK_IDS = ["DBPe", "DBPL", "SHK", "SHK2", "MST1", "MST2", "MSPL", "NSG"]
CCYS = ("HKD", "SGD")

_TRANSFER_TYPES = ("Transfer-In", "Transfer-Out")


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
    # Deliberately never interpolates a balance, price or narrative: a failure
    # here should not print holdings to a terminal or a CI log.
    print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")
    return False


def _bank_refs(db):
    return {
        b: db.execute(
            "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (b,)
        ).fetchone()["ref_num"]
        for b in BANK_IDS
    }


def _sheet_positions(db, bank_ref, bank_id, ccy, report_date, hkd_wd):
    """The positions actually written to one bank/currency sheet -- the
    balance-derived rows plus the ACCU-only placeholders, exactly as
    excel_writer.build_workbook assembles them."""
    accu = [r for r in contract_records(db, bank_ref, "ACCU") if r["ccy_id"] == ccy]
    positions = position_records(db, bank_ref, bank_id, ccy, report_date, hkd_wd=hkd_wd)
    return inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date)


def _week_monday(report_date):
    return report_date - timedelta(days=report_date.isoweekday() - 1)


def _as_of(report_date, hkd_wd):
    """The date the sheet's "AS OF" header names, and the date the beginning
    balance is snapshotted on."""
    return hkd_wd.previous_day(position_start_date(report_date, hkd_wd))


def _fridays_of_2026():
    d = date(2026, 1, 2)
    out = []
    while d <= date(2026, 9, 4):
        out.append(d)
        d += timedelta(days=7)
    return out


def _balance(db, bank_ref, code_ref, on_date):
    return db.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM tbl_transaction "
        "WHERE bank_ref = ? AND code_ref = ? AND trade_date <= ?",
        (bank_ref, code_ref, on_date.isoformat())
    ).fetchone()[0]


def _flat_start_cases(db, refs, hkd_wd, report_dates):
    """Every (report_date, bank, currency, code) that held nothing on the AS-OF
    date but traded during the reported week -- the shape that used to vanish
    from the report entirely. Returned newest first.

    Codes carrying an ACCU contract on that sheet are excluded: they get a
    placeholder row from inject_accu_only_positions whether or not this bug is
    fixed, so a case picked from them would pass against the old code too and
    pin nothing. The criterion is drawn from the data, not from the fix."""
    cases = []
    for report_date in report_dates:
        monday = _week_monday(report_date)
        as_of = _as_of(report_date, hkd_wd)
        for bank_id in BANK_IDS:
            bank_ref = refs[bank_id]
            for ccy in CCYS:
                rescued = {r["code"] for r in contract_records(db, bank_ref, "ACCU")
                           if r["ccy_id"] == ccy}
                traded = db.execute(
                    "SELECT s.ref_num AS code_ref, s.code, "
                    "       GROUP_CONCAT(DISTINCT t.transaction_type) AS types "
                    "FROM tbl_transaction t "
                    "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
                    "INNER JOIN tbl_currency cy ON cy.ref_num = s.ccy_ref "
                    "WHERE t.bank_ref = ? AND cy.ccy_id = ? "
                    "AND t.trade_date >= ? AND t.trade_date <= ? "
                    "GROUP BY s.ref_num",
                    (bank_ref, ccy, monday.isoformat(), report_date.isoformat()),
                ).fetchall()
                for row in traded:
                    if row["code"] in rescued:
                        continue
                    if _balance(db, bank_ref, row["code_ref"], as_of) != 0:
                        continue
                    cases.append({
                        "report_date": report_date,
                        "bank_id": bank_id,
                        "bank_ref": bank_ref,
                        "ccy": ccy,
                        "code": row["code"],
                        "code_ref": row["code_ref"],
                        "types": set((row["types"] or "").split(",")),
                        "ending": _balance(db, bank_ref, row["code_ref"], report_date),
                    })
    cases.reverse()
    return cases


def _expected_ending(balance):
    """How _transactions_narrative spells its running total."""
    return "= " + "{:,.0f}".format(balance)


def main():
    ctx, db = _open()
    try:
        ok = True
        refs = _bank_refs(db)
        hkd_wd = WorkingDay(db, "HKD")
        report_dates = _fridays_of_2026()
        cases = _flat_start_cases(db, refs, hkd_wd, report_dates)

        if not cases:
            print("  FAIL: no flat-start trading week found in the sample period;")
            print("        this harness has nothing to pin. Widen _fridays_of_2026().")
            sys.exit(1)

        # --- Case A: the reported shape. A code transferred into an account that
        # held none of it must render on the receiving sheet, with a zero
        # beginning balance and a narrative whose running total is what arrived.
        incoming = next((c for c in cases if "Transfer-In" in c["types"]), None)
        ok &= _case("A0 a Transfer-In into a flat account exists to test",
                    incoming is not None, True)
        if incoming:
            sheet = _sheet_positions(db, incoming["bank_ref"], incoming["bank_id"],
                                     incoming["ccy"], incoming["report_date"], hkd_wd)
            rec = sheet.get(incoming["code"])
            ok &= _case("A1 receiving row exists", rec is not None, True)
            ok &= _case("A2 receiving beginning balance is zero",
                        rec["balance"] if rec else None, 0)
            ok &= _case("A3 narrative names the Transfer-In",
                        "Transfer-In" in (rec["transactions"] or "") if rec else None,
                        True)
            ok &= _case("A4 narrative total is the shares that arrived",
                        (rec["transactions"] or "").endswith(
                            _expected_ending(incoming["ending"])) if rec else None,
                        True)

            # --- Case B: the paying leg is unchanged. It held the shares on the
            # AS-OF date, so it was always emitted; this guards the fix against
            # disturbing the side of the transfer that already worked.
            in_leg = db.execute(
                "SELECT trade_date, counter_bank_ref FROM tbl_transaction "
                "WHERE bank_ref = ? AND code_ref = ? AND transaction_type = 'Transfer-In' "
                "AND trade_date >= ? AND trade_date <= ? "
                "AND counter_bank_ref IS NOT NULL LIMIT 1",
                (incoming["bank_ref"], incoming["code_ref"],
                 _week_monday(incoming["report_date"]).isoformat(),
                 incoming["report_date"].isoformat())
            ).fetchone()
            out_leg = None
            if in_leg:
                out_leg = db.execute(
                    "SELECT t.bank_ref, b.bank_id FROM tbl_transaction t "
                    "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
                    "WHERE t.code_ref = ? AND t.transaction_type = 'Transfer-Out' "
                    "AND t.trade_date = ? AND t.bank_ref = ? LIMIT 1",
                    (incoming["code_ref"], in_leg["trade_date"],
                     in_leg["counter_bank_ref"])
                ).fetchone()
            ok &= _case("B0 the paying leg was found", out_leg is not None, True)
            if out_leg:
                as_of = _as_of(incoming["report_date"], hkd_wd)
                expected_open = _balance(db, out_leg["bank_ref"],
                                         incoming["code_ref"], as_of)
                expected_close = _balance(db, out_leg["bank_ref"],
                                          incoming["code_ref"], incoming["report_date"])
                sheet = _sheet_positions(db, out_leg["bank_ref"], out_leg["bank_id"],
                                         incoming["ccy"], incoming["report_date"], hkd_wd)
                rec = sheet.get(incoming["code"])
                ok &= _case("B1 paying row exists", rec is not None, True)
                ok &= _case("B2 paying beginning balance is the AS-OF holding",
                            rec["balance"] if rec else None, expected_open)
                ok &= _case("B3 paying narrative names the Transfer-Out",
                            "Transfer-Out" in (rec["transactions"] or "") if rec else None,
                            True)
                ok &= _case("B4 paying narrative total is what remains",
                            (rec["transactions"] or "").endswith(
                                _expected_ending(expected_close)) if rec else None,
                            True)

        # --- Case C: not a transfer. The same disappearance arises when an
        # account simply buys into a code it held none of, so the fix cannot be
        # scoped to transfer transaction types.
        bought = next((c for c in cases
                       if not (c["types"] & set(_TRANSFER_TYPES)) and c["ending"] != 0),
                      None)
        ok &= _case("C0 a purchase into a flat position exists to test",
                    bought is not None, True)
        if bought:
            sheet = _sheet_positions(db, bought["bank_ref"], bought["bank_id"],
                                     bought["ccy"], bought["report_date"], hkd_wd)
            rec = sheet.get(bought["code"])
            ok &= _case("C1 row exists for a purchase into a flat position",
                        rec is not None, True)
            ok &= _case("C2 beginning balance is zero",
                        rec["balance"] if rec else None, 0)
            ok &= _case("C3 narrative total is the resulting holding",
                        (rec["transactions"] or "").endswith(
                            _expected_ending(bought["ending"])) if rec else None,
                        True)

        # --- Case D (structural): over every sheet of every weekly report of 2026,
        # a code that traded during the reported week must appear on that sheet.
        # Stated as a property of the report rather than of these codes, so no
        # amount of per-case patching can satisfy it.
        absent = []
        for report_date in report_dates:
            monday = _week_monday(report_date)
            for bank_id in BANK_IDS:
                bank_ref = refs[bank_id]
                for ccy in CCYS:
                    traded = db.execute(
                        "SELECT DISTINCT s.code FROM tbl_transaction t "
                        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref "
                        "INNER JOIN tbl_currency cy ON cy.ref_num = s.ccy_ref "
                        "WHERE t.bank_ref = ? AND cy.ccy_id = ? "
                        "AND t.trade_date >= ? AND t.trade_date <= ?",
                        (bank_ref, ccy, monday.isoformat(), report_date.isoformat()),
                    ).fetchall()
                    if not traded:
                        continue
                    sheet = _sheet_positions(db, bank_ref, bank_id, ccy, report_date, hkd_wd)
                    for row in traded:
                        if row["code"] not in sheet:
                            absent.append((report_date, bank_id, ccy))
        ok &= _case("D traded-this-week codes absent from their sheet", len(absent), 0)

        # --- Case E (structural): the converse. Widening emission must not put
        # rows on a sheet that have nothing to say -- every emitted row must carry
        # either a beginning balance or a narrative, unless it is an ACCU-only
        # placeholder (which exists to show the contract, not a holding).
        empty = []
        for report_date in report_dates:
            for bank_id in BANK_IDS:
                bank_ref = refs[bank_id]
                for ccy in CCYS:
                    accu_codes = {
                        r["code"] for r in contract_records(db, bank_ref, "ACCU")
                        if r["ccy_id"] == ccy
                    }
                    rows = position_records(db, bank_ref, bank_id, ccy, report_date,
                                            hkd_wd=hkd_wd)
                    for code, r in rows.items():
                        if not r["balance"] and not r["transactions"] and code not in accu_codes:
                            empty.append((report_date, bank_id, ccy))
        ok &= _case("E emitted rows with neither balance nor narrative", len(empty), 0)
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
