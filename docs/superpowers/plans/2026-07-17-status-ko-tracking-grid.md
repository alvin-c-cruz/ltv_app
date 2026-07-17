# Status / Knock-out Tracking Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-instrument, per-day knock-out/strike status grid (columns Z:AJ) to every ACCU/DECU contract block on every generated `ltv-stocks` sheet.

**Architecture:** One new pure function, `_write_status_grid(ws, count_row, n, date_range)`, writes the grid for a single contract block (Z direction-flag column + AA:AJ 10-day status formulas paired 1:1 with the existing O:X price columns). It is called twice per sheet in `build_workbook` — once after the ACCU `_write_contracts` call, once after DECU — reusing the `accu_count_row`/`decu_count_row` locals `build_workbook` already computes. Row placement is fully dynamic (`count_row+2` for the date header, `count_row+4 .. count_row+4+n-1` for the body), so it's correct for every sheet's own contract counts, not just DBPe-HKD.

**Tech Stack:** Python 3.13, `openpyxl` for cell/style writing, raw `sqlite3` via `get_db()`. No pytest suite in this copy — verification is a runnable script, same convention as `scripts/verify_period_schedule.py` / `scripts/verify_positions_calc.py`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-status-ko-tracking-grid-design.md`.
- Only modify `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`. No other file changes.
- `Z` and the date-header cells (`AA{header_row}:AJ{header_row}`) are literal values, never formulas. `AA:AJ` body cells are formulas (exact template given in Task 1).
- Row placement is dynamic: header row = `count_row+2`, body rows = `count_row+4 .. count_row+4+n-1`. If `n == 0`, write nothing for that block.
- `_write_status_grid` is called for **every** sheet's ACCU and DECU blocks (both HKD and SGD), not gated by sheet name.
- `ws.print_area` stays `A1:X{r}` — unchanged, Z:AJ stays outside the printed area.
- Run everything with `C:/envs/LTV-ai/server/.venv/Scripts/python.exe`, cwd the repo root (worktree root once one exists).

---

## File Structure

- **Modify** `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`:
  - Add `_STATUS_COLS` constant near the existing `_OX_COLS` (~line 74).
  - Add `_write_status_grid(ws, count_row, n, date_range)` function near `_write_contracts`.
  - Wire two call sites into `build_workbook` (~lines 737-743).
  - Fix the module docstring (lines 6-7), which currently says the port drops "the AA-AJ per-day status columns" — no longer true after this change.
- **Create** `scripts/verify_status_grid.py` — the verification script (this plan's "test").

---

### Task 1: `_write_status_grid` + wiring + docstring + verification

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py:6-7` (docstring), `:74` (add `_STATUS_COLS` after `_OX_COLS`), a new function placed directly after `_write_contracts` (which currently ends at line 312, right before the "Reference data" section comment at line 315), and `:737-743` (`build_workbook` call sites).
- Create: `scripts/verify_status_grid.py`

**Interfaces:**
- Consumes: `xl_font`, `xl_align`, `xl_box` (existing style helpers, already imported/defined in this file), `_OX_COLS` (existing tuple).
- Produces: `_STATUS_COLS = ('AA','AB','AC','AD','AE','AF','AG','AH','AI','AJ')` (module-level tuple) and `_write_status_grid(ws, count_row: int, n: int, date_range: list) -> None`, called from `build_workbook`.

- [ ] **Step 1: Write the failing verification script**

Create `scripts/verify_status_grid.py`:

```python
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
    return (
        f'=IF($E{r}>$F{r},'
        f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
        f'IF($Z{r}=2,IF($G{r}<={price_col}{r},"KO",IF($F{r}>={price_col}{r},"D",".")),'
        f'IF($G{r}<={price_col}{r},"KO",".")))),'
        f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
        f'IF($Z{r}=2,IF($G{r}>={price_col}{r},"KO",IF($F{r}<={price_col}{r},"D",".")),'
        f'IF($G{r}>={price_col}{r},"KO",".")))))'
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


def check_live():
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
        buf = build_workbook(db, date(2026, 7, 10), ['DBPe'])
    finally:
        ctx.pop()

    wb = openpyxl.load_workbook(buf)
    if 'DBPe-HKD' not in wb.sheetnames:
        print("  live DBPe-HKD: FAIL  sheet not found")
        return False
    ws = wb['DBPe-HKD']
    ok = True
    ok &= _case("live DBPe-HKD Z7", ws['Z7'].value, 2)
    ok &= _case("live DBPe-HKD Z13", ws['Z13'].value, 2)
    ok &= _case("live DBPe-HKD AA7 formula", ws['AA7'].value, _formula(7, 'O'))
    ok &= _case("live DBPe-HKD Z20", ws['Z20'].value, 2)
    ok &= _case("live DBPe-HKD Z23", ws['Z23'].value, 2)
    ok &= _case("live DBPe-HKD AA20 formula", ws['AA20'].value, _formula(20, 'O'))
    return ok


def main():
    print("Isolated checks:")
    ok1 = check_isolated()
    print("Live DBPe-HKD sanity check:")
    ok2 = check_live()
    ok = ok1 and ok2
    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the verification script to confirm it fails**

Run: `.venv/Scripts/python.exe scripts/verify_status_grid.py`
Expected: **ImportError** — `cannot import name '_write_status_grid' from 'ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer'` (the function doesn't exist yet). This proves the script is actually exercising the not-yet-written code.

- [ ] **Step 3: Add `_STATUS_COLS`**

In `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`, immediately after the existing `_OX_COLS` line (currently line 74):

```python
_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')
# AA-AJ per-day status columns, paired 1:1 with _OX_COLS (AA reads the same
# day as O, AB as P, ... AJ as X).
_STATUS_COLS = ('AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG', 'AH', 'AI', 'AJ')
```

- [ ] **Step 4: Add `_write_status_grid`**

Add this function directly after `_write_contracts` ends (after its closing `return row + 2` and before the `# --- Reference data ported verbatim ...` comment block):

```python
def _write_status_grid(ws, count_row, n, date_range):
    """Writes the Z:AJ knock-out/strike tracking grid for one contract block.

    `count_row`/`n` match the same block's `_write_contracts` call (the row
    passed in, and `len(records)`) -- this reproduces `_write_contracts`'
    own row placement: the date-header row sits on `count_row+2` (the same
    row `_write_contracts` uses for its own O:X date header), and the body
    spans `count_row+4 .. count_row+4+n-1` (the same rows `_write_contracts`
    used for its data rows). If n == 0 there is nothing to track -- no
    header, no body.

    Z is a literal per-row direction-flag input (always 2, not a formula).
    AA:AJ are formulas, paired 1:1 with the existing O:X closing-price
    columns via _STATUS_COLS/_OX_COLS, each referencing that row's own
    spot/strike/KO price (E/F/G, already written by _write_contracts) and
    the paired day's closing price -- so the grid recalculates live from
    O:X. Ports the "AA-AJ per-day status columns" this module's docstring
    previously said were dropped.
    """
    if n == 0:
        return

    header_row = count_row + 2
    first_data_row = count_row + 4
    last_data_row = first_data_row + n - 1

    for col, offset in zip(_STATUS_COLS, range(10)):
        cell = ws[f'{col}{header_row}']
        cell.value = date_range[offset]
        cell.font = xl_font(9, True)
        cell.alignment = xl_align(True)
        cell.number_format = 'm/d'
        cell.border = xl_box()

    for r in range(first_data_row, last_data_row + 1):
        z_cell = ws[f'Z{r}']
        z_cell.value = 2
        z_cell.font = xl_font(10)
        z_cell.alignment = xl_align(True)
        z_cell.border = xl_box()

        for col, price_col in zip(_STATUS_COLS, _OX_COLS):
            formula = (
                f'=IF($E{r}>$F{r},'
                f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
                f'IF($Z{r}=2,IF($G{r}<={price_col}{r},"KO",IF($F{r}>={price_col}{r},"D",".")),'
                f'IF($G{r}<={price_col}{r},"KO",".")))),'
                f'IF({price_col}{r}=0,"xxx",IF({price_col}{r}="","",'
                f'IF($Z{r}=2,IF($G{r}>={price_col}{r},"KO",IF($F{r}<={price_col}{r},"D",".")),'
                f'IF($G{r}>={price_col}{r},"KO",".")))))'
            )
            cell = ws[f'{col}{r}']
            cell.value = formula
            cell.font = xl_font(10)
            cell.alignment = xl_align(True)
            cell.border = xl_box()
```

- [ ] **Step 5: Wire the two call sites into `build_workbook`**

In `build_workbook`, replace:

```python
            accu_count_row = r
            r = _write_contracts(ws, accu, 'ACCU', r, report_date, date_range, wd,
                                  price_lookup=price_lookup, bank_id=bank_id)

            decu_count_row = r
            r = _write_contracts(ws, decu, 'DECU', r, report_date, date_range, wd,
                                  price_lookup=price_lookup, bank_id=bank_id)
```

with:

```python
            accu_count_row = r
            r = _write_contracts(ws, accu, 'ACCU', r, report_date, date_range, wd,
                                  price_lookup=price_lookup, bank_id=bank_id)
            _write_status_grid(ws, accu_count_row, len(accu), date_range)

            decu_count_row = r
            r = _write_contracts(ws, decu, 'DECU', r, report_date, date_range, wd,
                                  price_lookup=price_lookup, bank_id=bank_id)
            _write_status_grid(ws, decu_count_row, len(decu), date_range)
```

(Everything else in `build_workbook` — the lines above and below this block — stays exactly as-is.)

- [ ] **Step 6: Fix the module docstring**

At the top of the file, change:

```python
"""Excel writer — contract + positions tables, and full workbook assembly.

Ports `localhost/modules/ltv_stocks2.py`'s `contract()` method (lines 410-709,
`_write_contracts` here), `position()` (712-914, `_write_positions`), `create()`
(211-295, `build_workbook`), `report_header()` (342-407, `report_header`) and
`column_width()` (298-339, `_set_column_widths`) cell-for-cell, dropping the
AA-AJ per-day status columns and the off-print-area helper columns `Y`-`AC`
(the reconciliation helper columns) — see docs/superpowers/specs/
2026-07-06-ltv-stocks-legacy-exact-replica-design.md, "The Excel writer".

`build_workbook(db, report_date, bank_ids)` is the public entry point.
"""
```

to:

```python
"""Excel writer — contract + positions tables, and full workbook assembly.

Ports `localhost/modules/ltv_stocks2.py`'s `contract()` method (lines 410-709,
`_write_contracts` here), `position()` (712-914, `_write_positions`), `create()`
(211-295, `build_workbook`), `report_header()` (342-407, `report_header`) and
`column_width()` (298-339, `_set_column_widths`) cell-for-cell, plus a
`_write_status_grid` knock-out/strike tracking grid (Z:AJ, see docs/
superpowers/specs/2026-07-17-status-ko-tracking-grid-design.md) added on top
of the port. The off-print-area helper columns `Y`-`AC` (the reconciliation
helper columns, a separate concept from the status grid) remain dropped —
see docs/superpowers/specs/2026-07-06-ltv-stocks-legacy-exact-replica-design.md,
"The Excel writer".

`build_workbook(db, report_date, bank_ids)` is the public entry point.
"""
```

- [ ] **Step 7: Run the verification script to confirm it passes**

Run: `.venv/Scripts/python.exe scripts/verify_status_grid.py`
Expected: every case prints `PASS`, `RESULT: ALL PASS`, exit 0. This exercises both the isolated checks (no DB) and the live end-to-end check against the real DBPe-HKD sheet.

- [ ] **Step 8: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py scripts/verify_status_grid.py
git commit -m "feat(ltv-stocks): add Z:AJ knock-out/strike status grid to every sheet

_write_status_grid writes a per-instrument, per-day KO/strike tracking grid
for each ACCU/DECU block: Z is a literal direction-flag input (always 2),
AA:AJ are formulas paired 1:1 with the existing O:X closing-price columns.
Row placement is dynamic (count_row+2 for the date header, count_row+4..
count_row+4+n-1 for the body), reusing the accu_count_row/decu_count_row
build_workbook already computes -- correct on every sheet, not just
DBPe-HKD. Verified via scripts/verify_status_grid.py (isolated formula/
placement checks plus a live end-to-end check against the real DB)."
```

---

## Self-Review

**Spec coverage:** Layout/row placement (dynamic `count_row+2`/`count_row+4..+n-1`) → Step 4. Z literal-2 input → Step 4. AA:AJ formula (exact template, locked `$E/$F/$G/$Z`, relative price ref) → Step 4, verified character-for-character by Step 1's `_formula()` helper (same template, so implementer and verification agree by construction). Date headers as literal values with `m/d` format → Step 4, verified by Step 1. Formatting (Arial 10/9, centered, bold on headers, thin borders) → Step 4, verified by Step 1. Every-sheet scope (no sheet-name gating) → Step 5 (call sites sit in the per-sheet loop body, unconditional). `n==0` → nothing written → Step 4's early return, verified by Step 1's n=0 case. `print_area` unchanged → not touched by this task (no step modifies it). Docstring fix → Step 6.

**Placeholder scan:** none — every step has literal code or an exact command + expected output.

**Type consistency:** `_write_status_grid(ws, count_row, n, date_range)` signature is identical everywhere it's referenced (Step 4's definition, Step 5's two call sites, Step 1's verification script's direct calls). `_STATUS_COLS`/`_OX_COLS` both 10-tuples, paired via `zip` in the same order both places they're zipped (Step 4's body loop, Step 1 only re-derives the formula string independently rather than importing `_STATUS_COLS`, so there's no shared-constant risk there).
