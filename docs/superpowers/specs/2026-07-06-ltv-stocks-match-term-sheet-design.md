# LTV Stocks Report — Match the Term-Sheet Contract Listing

**Date:** 2026-07-06
**Status:** ⚠️ SUPERSEDED by `2026-07-06-ltv-stocks-reuse-termsheet-records-design.md`
(this SQL-patching approach was replaced by reusing term-sheet's `StockContract` model).
**Scope:** `ltv_app/blueprints/ltv_stocks/` (Excel download only)
**Supersedes:** the current-week DONE/KO filter from
[2026-07-02-ltv-stocks-current-week-done-ko-filter-design.md](2026-07-02-ltv-stocks-current-week-done-ko-filter-design.md)

## Problem

The ACCU/DECU sections of the downloaded LTV Stocks Excel are meant to show the same
contracts as the term-sheet page (`/term-sheet/<bank>`), which lists every non-inactive
contract for a bank. In practice the Excel shows **almost none of them**.

Root cause: `_load_contracts` (and `_get_blocked_map`) count *received* contract periods with
`COUNT(p.ref_num)` — the count of **all** period rows. But `CreateSchedules` pre-generates the
entire contract schedule up front, so that count equals the whole life of the contract. This
makes `remaining = max(0, total - received)` collapse to 0, so nearly every contract is flagged
**DONE**; the current-week filter then drops the DONE ones. Net effect: active contracts vanish
from the report.

The same miscount silently zeroes every DECU's **blocked** shares in the Positions section
(`remaining == 0` ⇒ `continue`), so Positions reports full "unblocked" everywhere.

### Evidence (live data, DBPe ACCU, report date 2026-07-06)

| Reference | tenor/freq | scheduled periods (counted now) | received (`received != ''`) | formula total | current verdict | correct verdict |
|---|---|---|---|---|---|---|
| Alibaba-6 | 12m bi | 26 | 20 | 24 | remaining 0 → DONE → dropped | remaining > 0 → active |
| China Molybdenum-19 | 12m bi | 26 | 3 | 24 | DONE → dropped | active |
| HK Exchange-18 | 12m bi | 26 | 3 | 24 | DONE → dropped | active |

All 7 DBPe ACCU contracts (active on term-sheet) are dropped from the Excel today. Every DECU's
blocked shares compute to 0 (e.g. Geely-7 should be 42,000; China Molybdenum-4 should be 19,176).

The database is not the issue: both surfaces read the same unified DB
(`get_db()` → `current_app.config['DATABASE']` = `instance/LTV Stocks.db`, `ltv_app/__init__.py:24`).

## Requirements

1. **Received periods are counted correctly.** In both `_load_contracts` and `_get_blocked_map`,
   "received" = periods where `received` is non-null and not the empty string, not the total
   scheduled period count.
2. **The Excel lists the same non-inactive set as term-sheet.** Remove the current-week DONE/KO
   filter so all `status != 'inactive'` contracts appear (active + DONE + KO), for both ACCU and
   DECU.
3. **Positions blocked shares are correct.** With Req 1 applied to `_get_blocked_map`, active
   DECUs with unreceived periods contribute real blocked shares.
4. **Stock names carry the GTD suffix**, exactly as term-sheet renders it:
   - `gtd == "No"` → `"{stock} No GTD"`
   - `gtd == "Yes"` → `"{stock} GTD 1m"`
   - otherwise (`"1m"`, `"2m"`, …) → `"{stock} GTD {gtd}"`
   - missing/empty `gtd` → plain stock name (defensive; term-sheet assumes gtd is always set).
5. The A3 **active count** (contracts that are neither DONE nor KO) and column-M `DONE`
   rendering are unchanged in behavior. DONE/KO rows now appear in the listing but are still
   excluded from the active count.

### Out of scope

- The web view (`/ltv-stocks/`) stays download-only; no on-page tables.
- **Exact month values.** Received/Remaining/Total months keep ltv-stocks' existing
  `tenor × frequency` formula, which can differ slightly from term-sheet's per-period math
  (a 12m bi-monthly generates 26 scheduled periods but the formula assumes 24). This spec makes
  the *classification* (active vs DONE) and *which contracts appear* correct; it does not mirror
  term-sheet's exact period arithmetic. A future change could reuse term-sheet's accounting if
  exact month parity is required.
- No "KO" indicator in the Next Date column, no Reference column, no header rename — those were
  considered and declined for this change.
- No schema/data changes. `legacy_excel_generator.py` (unused) untouched.

### Trade-off accepted

Removing the current-week filter reverses commit `d220f38`: DONE and KO contracts will again
accumulate in the report indefinitely rather than dropping off after their trade week. This is
the intended behavior for this change (parity with term-sheet).

## Affected code & access policy

- **Data layer:** `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`
  - `_load_contracts` (line ~58), `_get_blocked_map` (line ~225), `get_ltv_stocks_full`
    (line ~14), and `_parse_trade_date` (line ~50, to be deleted).
- **Excel renderer:** `ltv_app/blueprints/ltv_stocks/views.py` — `_generate_excel` /
  `_xl_contracts` / `_xl_positions`. **Unchanged** (already reads `contract['stock_name']`).
- **GTD reference implementation:** `ltv_app/blueprints/term_sheet/models.py:summary`
  (lines 143–149).
- **Tables (read-only):** `tbl_stock_contract`, `tbl_stock_contract_period`,
  `tbl_bank_account`, `tbl_code`, `tbl_currency`, `tbl_stock_price`.
- **Routes** (in `ltv_app/blueprints/ltv_stocks/views.py`), unchanged by this spec:
  `home` (`/ltv-stocks/`, GET/POST) and `download` (`/ltv-stocks/download`, POST). Both are
  `@login_required` and accessible to **all authenticated levels (1=admin … 5=viewer)**,
  read-only. Unauthenticated requests redirect to the login page (Flask-Login default).
  No `@superuser_required` gating; this change adds no routes and alters no access policy.

## Design

All changes are in `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py`. No changes to
`views.py` (the Excel renderer already writes `contract['stock_name']` into the Stock Name
column, so the GTD suffix flows through with no renderer edit).

### 1. Correct received-period counting (both queries)

In `_load_contracts` and `_get_blocked_map`, replace:

```sql
COUNT(p.ref_num) AS received_count
```

with:

```sql
COALESCE(SUM(CASE WHEN p.received IS NOT NULL AND p.received != '' THEN 1 ELSE 0 END), 0) AS received_count
```

The `LEFT JOIN tbl_stock_contract_period` and `GROUP BY c.ref_num` are unchanged; a contract
with no periods yields `received_count = 0`.

### 2. Remove the current-week DONE/KO filter (`_load_contracts`)

- Change the signature `_load_contracts(db, result, price_map, report_date)` →
  `_load_contracts(db, result, price_map)`.
- Delete the `week_start`/`week_end` computation and the
  `if is_done or is_ko: … continue` block.
- Remove `c.trade_date` from the SELECT and delete the now-unused `_parse_trade_date` helper.
- Update the caller `get_ltv_stocks_full` to `_load_contracts(db, result, price_map)`
  (`report_date` is still used elsewhere in that function for prices/positions/transactions).
- `is_done` / `is_ko` are still computed (used by `next_date`, the `is_ko` flag, and the active
  count) — only the filtering on them is removed.

### 3. GTD suffix on stock names (`_load_contracts`)

- Add `c.gtd` to the SELECT.
- Add a module-level helper:

  ```python
  def _stock_name_with_gtd(stock_name, gtd):
      """Append the GTD term to the stock name, mirroring term_sheet's summary()."""
      if not gtd:
          return stock_name
      if gtd == "No":
          return f"{stock_name} No GTD"
      if gtd == "Yes":
          return f"{stock_name} GTD 1m"
      return f"{stock_name} GTD {gtd}"
  ```

- Set the contract's `'stock_name'` to `_stock_name_with_gtd(row['stock_name'], row['gtd'])`.
  (Contracts' `stock_name` is used only for the Excel Stock Name column; Positions build their
  own `stock_name` and are unaffected.)

### Edge cases

- **Contract with no period rows:** `received_count = 0` (via `COALESCE`), `remaining = total`
  → active. Same in `_get_blocked_map` (full blocked shares).
- **`gtd` NULL/empty:** plain stock name, no suffix (Req 4).
- **`gtd` outside {`No`, `Yes`, `Nm`}:** falls through to `"{stock} GTD {gtd}"`, mirroring
  term-sheet (no separate validation).
- **Report date with no non-inactive contracts for a bank:** `_xl_contracts` renders its
  existing "No active contracts." row — unchanged.
- The report is **read-only** (SELECT only); no INSERT/UPDATE paths, so no
  IntegrityError/OperationalError write handling is introduced.

## Convention compliance (CLAUDE.md)

- **No schema/data changes**, so no `localhost/` impact analysis is required.
- **DB access** stays via `get_db()` (the route passes the connection into the data layer);
  no direct `sqlite3.connect()` in application code.
- **Timezone:** the report date originates from `ph_today()` in
  `ltv_app/blueprints/ltv_stocks/views.py:home`; the data layer introduces no `datetime.now()`.
- **Positions numbers change:** the `_get_blocked_map` fix alters the Positions section's
  Blocked/Unblocked values. Explicitly approved by the user for this change.
- **Excel templating:** the LTV Stocks Excel is generated template-free (`Workbook()` in
  `views.py`) — a pre-existing deviation from the `instance/excel_templates/` convention. This
  spec does not touch Excel generation, so it neither introduces nor corrects that; a template
  conversion is out of scope.

## Testing

File: `tests/functional/test_ltv_stocks_active_count.py` (extend; some tests change).

- **Signature updates:** the two existing `_load_contracts(conn, result, {}, date(...))` calls
  drop the 4th arg.
- **Remove** `test_current_week_filters_done_and_ko` and `test_missing_trade_date_done_ko_omitted`
  (they asserted the now-removed filter).
- **Replace** with `test_done_and_ko_listed_regardless_of_trade_date`: a DONE and a KO contract
  with an out-of-any-week `trade_date` both appear in the listing.
- **New** `test_received_count_uses_received_flag_not_all_periods`: a contract with total = 2
  periods, one received (`received='1000'`) and one not (`received=''`), is **active**
  (`is_done is False`, `remaining > 0`) — under the old count it was DONE.
- **New** `test_blocked_map_counts_received_periods`: a DECU with unreceived periods yields
  blocked shares > 0 from `_get_blocked_map` (was 0 under the old count).
- **New** `test_stock_name_gtd_suffix`: `_stock_name_with_gtd` returns `"X No GTD"`,
  `"X GTD 1m"` (for `"Yes"`), `"X GTD 3m"` (for `"3m"`), and `"X"` for empty/None.
- Existing `test_load_contracts_sets_is_ko`, `test_ko_overrides_done_when_all_periods_received`,
  `test_active_count_excludes_done_and_ko`, `test_generate_excel_count_is_plain_integer` stay
  green (the `_add_contract` helper's period uses `received='1000'`, so it counts as received).

## Verification

1. Unit tests above (real temp SQLite).
2. Live spot check: download the report for `2026-07-06`; confirm the DBPe ACCU section now lists
   Alibaba-6/7, China Molybdenum-19, Geely-14, HK Exchange-18, Tencent-8/10 with GTD suffixes,
   and the Positions section shows non-zero Blocked shares for active DECUs.
