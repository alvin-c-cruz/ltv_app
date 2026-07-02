# LTV Stocks Report — Exclude KO Contracts from Active Count

**Date:** 2026-07-02
**Status:** Approved (design)
**Scope:** `ltv_app/blueprints/ltv_stocks/` (Excel download only)

## Problem

In the downloaded LTV Stocks Excel report, each bank sheet has an **ACCU** (Accumulator)
and a **DECU** (Decumulator) section. The first cell of each section (cell `A` on the
section's count row, referred to by the user as "A3") shows the number of **active**
contracts for that bank account.

Today that count is an Excel formula that only subtracts contracts marked `DONE`:

```python
# ltv_app/blueprints/ltv_stocks/views.py  (_xl_contracts)
formula = f'={len(contracts)}-COUNTIF(M{next_col_start}:M{next_col_end},"*DONE*")'
```

**KO (knocked-out) contracts are still counted as active.** They should not be.

## Definitions

- **DONE**: a contract that has received all its periods (`remaining == 0`). Shown with
  `"DONE"` in the next-month column (column M).
- **KO**: a contract whose stored status is `KO` (`tbl_stock_contract.status == 'KO'`).
  KO is an explicit, user-set status — **not** computed from prices. This matches the
  convention already used by the term_sheet report
  (`ltv_app/blueprints/term_sheet/models.py`).
- DONE and KO are **mutually exclusive** — a contract cannot be both. **KO takes
  precedence over the period-based DONE check:** a contract flagged `status == 'KO'`
  is treated as KO and never as DONE, *even if all its periods have been received*
  (`remaining == 0`). In practice all KO contracts in production have `remaining == 0`,
  so without this precedence they would render as "DONE"; the precedence rule is what
  keeps KO contracts showing a next-month date. Concretely: `is_done = remaining == 0
  and not is_ko`.
- **Active**: neither DONE nor KO.

## Requirements

1. The active count for each section (ACCU and DECU) must exclude both DONE and KO
   contracts. Count = number of contracts that are neither DONE nor KO.
2. The count cell must be a **plain integer computed in Python**, not an Excel formula.
   (A formula on column M cannot work because KO contracts show a date there, identical
   to active contracts.)
3. **DONE and KO contracts remain listed** in the report — they are not hidden.
4. **Column M** behavior is unchanged:
   - `"DONE"` for DONE contracts.
   - The computed next-month **date** for both active **and KO** contracts.
   (KO contracts show their next-month date, just like active ones.)

### Behavior matrix (per contract)

| State                                   | Listed in report? | Column M         | Counted in section count? |
|-----------------------------------------|-------------------|------------------|---------------------------|
| Active                                  | yes               | next-month date  | ✅ yes                    |
| KO (`status == 'KO'`)                   | yes               | next-month date  | ❌ no                     |
| DONE (`remaining == 0` and not KO)      | yes               | `"DONE"`         | ❌ no                     |

## Design

Two files change. No database schema changes.

### 1. `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `_load_contracts`

- Add `c.status` to the SELECT list.
- Add `is_ko` to each contract dict: `is_ko = (row['status'] == 'KO')`.
- Compute DONE with KO precedence: `is_done = remaining == 0 and not is_ko`.
- The `next_date` / column-M value: `'DONE'` when `is_done`, otherwise the computed
  next-month date. KO contracts are never `is_done`, so they fall into the "otherwise"
  branch and keep showing a date.

### 2. `ltv_app/blueprints/ltv_stocks/views.py` — `_xl_contracts`

- Replace the `COUNTIF` formula with a plain integer computed in Python:

  ```python
  active = sum(1 for ct in contracts if not ct['is_done'] and not ct['is_ko'])
  ```

  Write `active` to the section count cell (column A, section row 1) as a number.
- Column M rendering is unchanged: `"DONE"` for done contracts; a date for active and
  KO contracts.

Both the ACCU and DECU sections share `_load_contracts` and `_xl_contracts`, so both are
covered by the same change.

## Out of Scope

- No changes to the web view (`/ltv-stocks/`), which shows only positions.
- No changes to `legacy_excel_generator.py` (unused / not wired into the download route).
- No schema or data changes.
- No price-based KO detection — KO is read from the stored status only.

## Verification

Regenerate the report (e.g. Deutsche Bank) via the Download button and confirm:

1. A contract with `status == 'KO'` still shows its next-month **date** in column M and
   remains listed in its section.
2. A DONE contract still shows `"DONE"` and remains listed.
3. Each section's count cell is a **plain integer** equal to the number of contracts that
   are neither DONE nor KO.
4. Both ACCU and DECU sections behave identically.
