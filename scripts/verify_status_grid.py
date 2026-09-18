"""Verification for _write_status_grid (excel_writer.py).

Builds a fresh in-memory worksheet and calls _write_status_grid directly with
synthetic inputs (no DB needed -- the function only writes cells from
count_row/n/date_range, and the formulas it writes are pure cell references,
not value-dependent). Then does one live end-to-end sanity check against the
real DB, confirming the DBPe-HKD sheet's actual ACCU/DECU row placement
matches what the isolated checks predict.

Run: server/.venv/Scripts/python.exe scripts/verify_status_grid.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

import openpyxl

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import (
    _write_status_grid, build_workbook,
)

DATE_RANGE = [date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1),
              date(2026, 7, 2), date(2026, 7, 3), date(2026, 7, 6),
              date(2026, 7, 7), date(2026, 7, 8), date(2026, 7, 9),
              date(2026, 7, 10)]


def _formula(r, price_col):
    # The leading ISTEXT guard keeps the "KO" marker _write_contracts writes
    # into the O:X cell after a knock-out from being compared as a price --
    # Excel ranks text above every number. See scripts/verify_status_grid_ko_marker.py.
    return (
        f'=IF(ISTEXT({price_col}{r}),"",'
        f'IF($E{r}>$F{r},'
        f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
        f'IF($Z{r}=2,IF($G{r}<={price_col}{r},"KO",IF($F{r}>={price_col}{r},"D",".")),'
        f'IF($G{r}<={price_col}{r},"KO",".")))),'
        f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
        f'IF($Z{r}=2,IF($G{r}>={price_col}{r},"KO",IF($F{r}<={price_col}{r},"D",".")),'
        f'IF($G{r}>={price_col}{r},"KO",".")))))'
        f')'
    )


def _case(label, actual, expected):
    if actual == expected:
        print(f"  {label}: PASS")
        return True
    print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")
    return False


def check_isolated():
    ok = True
    wb = openpyxl.Workbook()
    ws = wb.active

    # ACCU-shaped block: count_row=3, n=7 -> header row 5, body rows 7-13.
    _write_status_grid(ws, count_row=3, n=7, date_range=DATE_RANGE)

    ok &= _case("ACCU header AA5 value", ws['AA5'].value, DATE_RANGE[0])
    ok &= _case("ACCU header AA5 number_format", ws['AA5'].number_format, 'm/d')
    ok &= _case("ACCU header AJ5 value", ws['AJ5'].value, DATE_RANGE[9])
    ok &= _case("ACCU Z7 value", ws['Z7'].value, 2)
    ok &= _case("ACCU Z13 value", ws['Z13'].value, 2)
    ok &= _case("ACCU AA7 formula", ws['AA7'].value, _formula(7, 'O'))
    ok &= _case("ACCU AJ13 formula", ws['AJ13'].value, _formula(13, 'X'))
    ok &= _case("ACCU AA6 untouched (above header)", ws['AA6'].value, None)
    ok &= _case("ACCU Z14 untouched (below body)", ws['Z14'].value, None)

    # DECU-shaped block: count_row=16, n=4 -> header row 18, body rows 20-23.
    _write_status_grid(ws, count_row=16, n=4, date_range=DATE_RANGE)

    ok &= _case("DECU header AA18 value", ws['AA18'].value, DATE_RANGE[0])
    ok &= _case("DECU Z20 value", ws['Z20'].value, 2)
    ok &= _case("DECU Z23 value", ws['Z23'].value, 2)
    ok &= _case("DECU AA20 formula", ws['AA20'].value, _formula(20, 'O'))

    # n=0 -> nothing written at all.
    _write_status_grid(ws, count_row=50, n=0, date_range=DATE_RANGE)
    ok &= _case("n=0 header untouched", ws['AA52'].value, None)
    ok &= _case("n=0 body untouched", ws['Z54'].value, None)

    return ok


BANK_ID = 'DBPe'
SHEET = 'DBPe-HKD'
CCY = 'HKD'
REPORT_DATE = date(2026, 7, 10)


def _check_block(ws, label, records, count_row, ok=True):
    """Assert one contract block sits exactly where `len(records)` says it does.

    `Z` is the literal 2 and `_formula()` is self-referential, so both hold at
    *every* contract row -- on their own they cannot tell a correctly derived
    row from one that is off by a contract. So this also pins each row to its
    own contract's code and prices, and asserts the rows immediately outside
    the block are untouched. An off-by-one in either direction then shows up.
    """
    n = len(records)
    if n == 0:
        # Newly reachable: knocked-out contracts are dropped, so a block can
        # empty. Indexing a zero-length block runs backwards over the header.
        print(f"  {label}: SKIP  no {label} contracts in the live DB")
        return ok

    first, last = count_row + 4, count_row + 3 + n

    ok &= _case(f"{label} Z{first} (first)", ws[f'Z{first}'].value, 2)
    ok &= _case(f"{label} Z{last} (last)", ws[f'Z{last}'].value, 2)
    ok &= _case(f"{label} AA{first} formula",
                ws[f'AA{first}'].value, _formula(first, 'O'))

    # Row-distinguishing: these differ between contracts, so landing on the
    # wrong row fails instead of passing.
    for row, rec, which in ((first, records[0], 'first'), (last, records[-1], 'last')):
        ok &= _case(f"{label} B{row} code ({which} contract)",
                    ws[f'B{row}'].value, rec['code'])
        ok &= _case(f"{label} G{row} K/O price ({which} contract)",
                    ws[f'G{row}'].value, rec['ko'])

    # Bounds: one row either side of the block belongs to no block at all.
    ok &= _case(f"{label} Z{first - 1} above the block is untouched",
                ws[f'Z{first - 1}'].value, None)
    ok &= _case(f"{label} Z{last + 1} below the block is untouched",
                ws[f'Z{last + 1}'].value, None)
    return ok


def check_live():
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
        from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records

        # Resolve the bank the same way build_workbook does, rather than
        # hardcoding a ref_num the check and the code under test could disagree on.
        bank_row = db.execute(
            "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (BANK_ID,)
        ).fetchone()
        if bank_row is None:
            print(f"  live {SHEET}: FAIL  bank_id {BANK_ID} not in tbl_bank_account")
            return False
        bank_ref = bank_row[0]

        accu = [r for r in contract_records(db, bank_ref, 'ACCU') if r['ccy_id'] == CCY]
        decu = [r for r in contract_records(db, bank_ref, 'DECU') if r['ccy_id'] == CCY]
        buf = build_workbook(db, REPORT_DATE, [BANK_ID])
    finally:
        ctx.pop()

    wb = openpyxl.load_workbook(buf)
    if SHEET not in wb.sheetnames:
        print(f"  live {SHEET}: FAIL  sheet not found")
        return False
    ws = wb[SHEET]

    # DBPe-HKD's report_header() shape always puts accu_count_row at 3;
    # _write_contracts places the first data row 4 below its count row and
    # returns first_data_row + n + 2.
    accu_count_row = 3
    decu_count_row = accu_count_row + 6 + len(accu)

    ok = _check_block(ws, 'ACCU', accu, accu_count_row)
    ok = _check_block(ws, 'DECU', decu, decu_count_row, ok)
    return ok


def check_discriminates():
    """The live check must be able to fail. Feeds it a roster one contract too
    long and confirms it says so -- otherwise the block-boundary assertions are
    passing vacuously, which is what they did before.
    """
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
        from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records
        bank_ref = db.execute(
            "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (BANK_ID,)
        ).fetchone()[0]
        accu = [r for r in contract_records(db, bank_ref, 'ACCU') if r['ccy_id'] == CCY]
        buf = build_workbook(db, REPORT_DATE, [BANK_ID])
    finally:
        ctx.pop()

    if len(accu) < 2:
        print("  SKIP  need at least 2 ACCU contracts to perturb")
        return True

    ws = openpyxl.load_workbook(buf)[SHEET]
    import contextlib
    import io as _io

    def detects(records):
        with contextlib.redirect_stdout(_io.StringIO()):
            return not _check_block(ws, 'ACCU', records, 3)

    ok = True
    # One too many: the derived last row falls past the block, into the gap.
    ok &= _case("a roster one contract too long is detected",
                detects(accu + [accu[-1]]), True)
    # One too few: the derived last row is still a real contract row, so `Z==2`
    # and the self-referential formula both hold there. Only the bound below
    # the block catches it -- this is the case the old assertions passed.
    ok &= _case("a roster one contract too short is detected",
                detects(accu[:-1]), True)
    return ok


def main():
    print("Isolated checks:")
    ok1 = check_isolated()
    print("Live DBPe-HKD sanity check:")
    ok2 = check_live()
    print("The live check can detect a wrong roster:")
    ok3 = check_discriminates()
    ok = ok1 and ok2 and ok3
    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
