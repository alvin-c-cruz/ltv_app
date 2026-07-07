import math
import os
import re
from datetime import date
import pytest
from openpyxl import load_workbook

GOLDEN = r"localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx"
LIVE_DB = r"instance/LTV Stocks.db"

pytestmark = pytest.mark.skipif(
    not (os.path.exists(GOLDEN) and os.path.exists(LIVE_DB)),
    reason="golden file or live DB not present")

# Positions 'average' cells hold a "=cost/balance" Excel formula string. Float
# summation order can differ by a sub-ULP amount between the legacy and ported
# code paths without being a real bug -- tolerate that inside the formula's
# two numeric operands, but keep everything else an exact string compare.
_FORMULA_RATIO_RE = re.compile(r'^=(.+)/(.+)$')


def _cell_equal(gv, ev):
    gs, es = str(gv), str(ev)
    if gs == es:
        return True
    gm, em = _FORMULA_RATIO_RE.match(gs), _FORMULA_RATIO_RE.match(es)
    if not (gm and em):
        return False
    try:
        g_num, g_den = float(gm.group(1)), float(gm.group(2))
        e_num, e_den = float(em.group(1)), float(em.group(2))
    except ValueError:
        return False
    return (math.isclose(g_num, e_num, rel_tol=1e-12)
            and math.isclose(g_den, e_den, rel_tol=1e-12))


def _cells(ws, max_col=24, max_row=None):
    out = {}
    for r in range(1, (max_row or ws.max_row) + 1):
        for c in range(1, max_col + 1):
            v = ws.cell(r, c).value
            if v is not None:
                out[(r, c)] = v
    return out


def _build():
    import sqlite3
    from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import build_workbook
    db = sqlite3.connect(LIVE_DB)
    db.row_factory = sqlite3.Row
    out = build_workbook(db, date(2026, 7, 6),
                         ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG'])
    db.close()
    return out


def _diff_sheet(got_wb, exp_wb, sheet_name):
    gws, ews = got_wb[sheet_name], exp_wb[sheet_name]
    diffs = []
    for (r, c), ev in _cells(ews).items():
        gv = gws.cell(r, c).value
        if not _cell_equal(gv, ev):
            diffs.append((gws.cell(r, c).coordinate, gv, ev))
    return diffs


def test_dbpe_hkd_matches_golden():
    out = _build()
    got = load_workbook(out)
    exp = load_workbook(GOLDEN)
    diffs = _diff_sheet(got, exp, 'DBPe-HKD')
    assert not diffs, f"{len(diffs)} cell diffs, first 10: {diffs[:10]}"


def test_shared_sheets_match_golden():
    out = _build()
    got = load_workbook(out)
    exp = load_workbook(GOLDEN)
    shared = [s for s in exp.sheetnames if s in got.sheetnames]
    all_diffs = {}
    for name in shared:
        diffs = _diff_sheet(got, exp, name)
        if diffs:
            all_diffs[name] = diffs
    assert not all_diffs, {k: (len(v), v[:10]) for k, v in all_diffs.items()}
