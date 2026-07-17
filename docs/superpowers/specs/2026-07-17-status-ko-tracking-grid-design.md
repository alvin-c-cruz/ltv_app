# Status / knock-out tracking grid — design

Date: 2026-07-17
Status: Approved

## Background

`legacy_port/excel_writer.py`'s module docstring documents that the port of
`ltv_stocks2.py`'s `contract()` method deliberately dropped "the AA-AJ
per-day status columns" when this generator was built. This spec adds that
capability back — a per-instrument, per-day knock-out/strike status grid —
for every ACCU/DECU contract block on every generated sheet, not just
DBPe-HKD (the sheet the request was authored against).

The row numbers originally given for this request (ACCU 7-13, DECU 20-23,
date headers on rows 5/18) are not independent facts: they are exactly what
`build_workbook`'s existing `accu_count_row`/`decu_count_row` values produce
for DBPe-HKD's current contract counts, via the same `count_row+4 ..
count_row+4+n-1` arithmetic `_write_contracts` already uses for its own data
rows, and `count_row+2` for its own date-header row. The design below makes
row placement dynamic from that existing arithmetic, which reproduces the
given numbers for DBPe-HKD today and produces correct positions for every
other sheet's own contract counts.

## Layout

Two independent blocks, one per contract product, each written by one call
to a new `_write_status_grid` function right after that product's existing
`_write_contracts` call in `build_workbook`:

- **ACCU block:** rows `accu_count_row+4 .. accu_count_row+4+len(accu)-1`.
  For DBPe-HKD today (`accu_count_row=3`, 7 contracts): rows 7-13.
- **DECU block:** rows `decu_count_row+4 .. decu_count_row+4+len(decu)-1`.
  For DBPe-HKD today (`decu_count_row=16`, 4 contracts): rows 20-23.
- **Date header row** for each block: `count_row+2` (the same row
  `_write_contracts` already uses for its own O:X date header — for
  DBPe-HKD today, row 5 for ACCU, row 18 for DECU). AA:AJ becomes a second,
  independent date-header block on that same row, different columns.

If a block has zero contracts (`n == 0`), nothing is written for that block
— no header, no body rows.

## Columns

- **Z** — per-row direction flag. Always the literal constant `2` (an input
  value, not a formula) on every data row in both blocks.
- **AA:AJ** — 10-day status matrix, one column per day, paired 1:1 with the
  existing `_OX_COLS` tuple (`O,P,Q,R,S,T,U,V,W,X`) via a new
  `_STATUS_COLS = ('AA','AB','AC','AD','AE','AF','AG','AH','AI','AJ')`
  tuple, so `AA` reads the same day as `O`, `AB` as `P`, etc.

## Formula (per body cell, row `r`, paired price column `p`)

```
=IF($E{r}>$F{r},
   IF({p}{r}=0,"xxx",IF({p}{r}="","",
      IF($Z{r}=2,IF($G{r}<={p}{r},"KO",IF($F{r}>={p}{r},"D",".")),
                 IF($G{r}<={p}{r},"KO",".")))),
   IF({p}{r}=0,"xxx",IF({p}{r}="","",
      IF($Z{r}=2,IF($G{r}>={p}{r},"KO",IF($F{r}<={p}{r},"D",".")),
                 IF($G{r}>={p}{r},"KO",".")))))
```

`E`/`F`/`G` are that row's spot/strike/knock-out price (already written by
`_write_contracts`); `{p}{r}` is that day's closing price in the paired
O:X column. `$E{r}`, `$F{r}`, `$G{r}`, `$Z{r}` are column-locked; the price
reference is relative (row-only, matching the row it's written on).

Output states: `"KO"` = knock-out barrier reached, `"D"` = strike triggered
(only reachable when `Z=2`), `"."` = active/no event, `"xxx"` = closing
price is 0 (placeholder/not traded), `""` = closing price cell blank
(future day, no data yet).

## Values vs. formulas

- **Z** and the **date header cells** (`AA{header_row}:AJ{header_row}`) are
  literal values — `2` for Z, the matching `date_range` entry for the
  header cells — matching how `_write_contracts` already writes its own
  O:X date header as literal values, not formulas.
- **AA:AJ body cells** are formulas (the expression above), so the grid
  recalculates live from the O:X closing prices already in the workbook,
  per the request.

## Formatting

- Body (`Z{first}:AJ{last}` for each block): Arial 10, centered, thin solid
  black borders on every cell — via the file's existing `xl_font`,
  `xl_align`, `xl_box` helpers.
- Date headers (`AA{header_row}:AJ{header_row}`): Arial 9, bold, centered,
  number format `"m/d"`, thin solid black borders.

## Scope / call sites

`_write_status_grid(ws, count_row, n, date_range)` is called twice per
sheet in `build_workbook`, immediately after each `_write_contracts` call
(ACCU, then DECU), using the `accu_count_row`/`decu_count_row` locals
`build_workbook` already computes for the existing cross-sheet-total
tracking. This applies the grid to every bank/ccy sheet that has ACCU
and/or DECU contracts (both HKD and SGD sheets), not only DBPe-HKD — no
sheet-name gating.

`ws.print_area` stays `A1:X{r}` (unchanged) — Z:AJ remains outside the
printed area, consistent with the module's existing "off-print-area helper
columns" precedent for columns beyond X.

## Housekeeping

Update the module docstring, which currently says the port drops "the
AA-AJ per-day status columns," to reflect that this specific KO-tracking
design adds that capability back (not necessarily identical to whatever the
original legacy version had — this is a fresh design against the formula
given in this spec).

## Verification

No automated test currently covers `excel_writer.py`'s cell-level output
(the existing `scripts/verify_positions_calc.py` harness covers
`positions_calc.py`'s data functions only). Verification for this change is
a one-off check: generate a real workbook via `build_workbook()` against the
live DB for a report date with known ACCU/DECU contract counts, then load
the result with `openpyxl` and assert the actual cell values/formulas/
number-formats in the Z:AJ range match this spec, for at least one sheet
with both ACCU and DECU contracts. Not added to the permanent regression
harness as part of this change.

## Out of scope

- The "off-print-area helper columns Y-AC (reconciliation helper columns)"
  the docstring also mentions as dropped — unrelated to this grid, stays
  dropped.
- Any change to `_write_contracts`, `_write_positions`, `report_header`, or
  `position_records`/`_average`/`_transactions_narrative`.
