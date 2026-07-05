# LTV Stocks Report — Current-Week Filter for DONE/KO Contracts

**Date:** 2026-07-02
**Status:** Approved (design)
**Scope:** `ltv_app/blueprints/ltv_stocks/` (Excel download only)
**Builds on:** [2026-07-02-ltv-stocks-active-count-ko-design.md](2026-07-02-ltv-stocks-active-count-ko-design.md)

## Problem

The ACCU and DECU sections of the downloaded LTV Stocks Excel currently list **every**
non-inactive contract — all Active, all DONE, and all KO contracts. Old completed/knocked-out
contracts accumulate and clutter the sections indefinitely.

The report should instead list:

1. All **Active** contracts (not DONE, not KO).
2. **DONE and KO** contracts only when they are *recent* — specifically when the contract's
   `trade_date` falls within the **current week** of the report date.

This supersedes the earlier decision to "show all DONE and KO contracts": DONE/KO contracts
now drop off the listing once their trade week has passed.

## Definitions

- **Current week**: Monday through Friday of the week containing `report_date`.
  - `week_start = report_date - timedelta(days=report_date.weekday())` (Monday)
  - `week_end = week_start + timedelta(days=4)` (Friday)
  - Inclusive on both ends. Holds for any `report_date`, including weekends (it resolves to
    the Mon–Fri of that calendar week).
- **Active / DONE / KO**: as defined in the active-count spec. DONE = `remaining == 0 and not KO`;
  KO = `status == 'KO'`; Active = neither.
- **`trade_date`**: the contract's own `tbl_stock_contract.trade_date` (its inception date),
  stored as an ISO `YYYY-MM-DD` string.

## Requirements

1. Active contracts are always listed (unchanged).
2. A DONE or KO contract is listed **only if** `week_start <= trade_date <= week_end`.
   Otherwise it is omitted from the section.
3. Applies to **both** the ACCU and DECU sections.
4. A DONE/KO contract with a missing or unparseable `trade_date` is treated as **not in the
   current week** (omitted) — DONE/KO contracts are the filtered set, and a contract we cannot
   place in time is not "recent".
5. The **A3 active count is unaffected**: it already counts active-only, and the filter only
   removes DONE/KO contracts that were never counted. (Regression-guard, not a new behavior.)
6. Column-M rendering and the plain-integer count from the prior spec are unchanged.

### Behavior matrix (per contract, per section)

| State  | Listed when trade_date in current week | Listed when trade_date outside current week |
|--------|----------------------------------------|---------------------------------------------|
| Active | yes (always, regardless of trade_date) | yes (always, regardless of trade_date)      |
| DONE   | yes                                    | no                                          |
| KO     | yes                                    | no                                          |

## Design

One file changes. No database schema changes.

### `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `_load_contracts`

- Change the signature from `_load_contracts(db, result, price_map)` to
  `_load_contracts(db, result, price_map, report_date)`.
- Add `c.trade_date` to the SELECT list.
- Compute the current-week window once at the top:
  ```python
  week_start = report_date - timedelta(days=report_date.weekday())
  week_end   = week_start + timedelta(days=4)
  ```
- In the per-row loop, after `is_done` / `is_ko` are known, skip the contract when it is
  DONE or KO and its `trade_date` is not within `[week_start, week_end]`:
  ```python
  if is_done or is_ko:
      td = _parse_trade_date(row['trade_date'])   # date or None
      if td is None or not (week_start <= td <= week_end):
          continue
  ```
- Add a small module-level helper `_parse_trade_date(value) -> date | None` that parses the
  first 10 chars of the value as an ISO date, returning `None` on failure (mirrors the existing
  defensive date parsing used for `start_date_raw` / `last_end_date_raw`).

### `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `get_ltv_stocks_full`

- Pass `report_date` into `_load_contracts(db, result, price_map, report_date)`.

`get_ltv_stocks` (the web/positions view) does not call `_load_contracts`, so it is untouched.

## Out of Scope

- No change to the web view (`/ltv-stocks/`), the positions section, or the weekly-transactions
  logic.
- No change to how DONE/KO is determined, to column M, or to the active count.
- No schema/data changes. `legacy_excel_generator.py` (unused) is untouched.
- No price-based logic.

## Verification

1. Unit test (real temp SQLite): seed an Active, a DONE, and a KO contract with a `trade_date`
   inside the current week, and a DONE and a KO contract with a `trade_date` outside it. Assert
   `_load_contracts` returns the Active always, the in-week DONE/KO, and omits the out-of-week
   DONE/KO.
2. Unit test: a DONE/KO contract with `trade_date = None` is omitted.
3. Live-data spot check: regenerate the report for 2026-07-02 and confirm the 4 KO contracts
   (trade_dates in May–June) are omitted, and that they appear when the report date is set to
   their own trade week.
