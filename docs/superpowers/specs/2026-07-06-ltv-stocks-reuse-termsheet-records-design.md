# LTV Stocks Report — Reuse Term-Sheet Record Logic in the Excel

**Date:** 2026-07-06
**Status:** Approved (design)
**Scope:** `ltv_app/blueprints/ltv_stocks/` (Excel download only)
**Supersedes:** `2026-07-06-ltv-stocks-match-term-sheet-design.md` (the SQL-patching approach) and the
current-week DONE/KO filter from `2026-07-02-ltv-stocks-current-week-done-ko-filter-design.md`.

## Problem

The downloaded LTV Stocks Excel maintains its **own** re-implementation of contract period
math (`_load_contracts` / `_get_blocked_map` in `create_ltv_stocks.py`), and that copy is buggy:
it counts *received* periods with `COUNT(p.ref_num)` (every scheduled row), so `remaining`
collapses to 0, active contracts are mislabeled **DONE** and dropped, and every DECU's **blocked**
shares compute to 0. Meanwhile the term-sheet page (`/term-sheet/<bank>`) already computes all of
this **correctly** from the `StockContract` model.

Rather than patch the parallel copy, the Excel should **reuse term-sheet's `StockContract`
implementation** so its ACCU/DECU records are identical to what `/term-sheet/<bank>` shows.

### What term-sheet's `StockContract` already computes correctly

In `ltv_app/blueprints/term_sheet/models.py`, `StockContract.__post_init__` / `as_dict()`:
- **Received periods** count only rows where `period['received']` is non-empty, then divide by the
  frequency factor (bi-monthly/bi-weekly = 2, weekly = 4) → months. `remaining = total − received`.
- **`next_date`** walks the periods → `"DONE"` when all received; `as_dict()` returns `"KO"` when
  `status == 'KO'`, else the next working-day date.
- **`remaining_shares`** = `remaining_days × daily_shares × (2 if leveraged)` — the blocked-share
  figure ltv-stocks currently gets as 0.
- Raw `spot`, `strike` (`spot×strike_rate/100`), `ko`, `start_date`, `end_date`, `reference`,
  `bank_doc`, and (via `summary()`'s rule) the GTD-suffixed stock name.

The term-sheet template (`term_sheet/home.html`) renders one table per **Accumulators** /
**Decumulators** listing every non-inactive contract, columns:
`Stock (GTD) | Code | Shares/Day | Spot | Strike | K/O | Start | End | Received | Remaining |
Total | Next Date | Contract No. (bank_doc) | Reference`, with KO rows highlighted and DONE/KO
shown in Next Date.

## Requirements

1. **Reuse the model.** The Excel's ACCU/DECU records are built from `StockContract` (its computed
   attributes), not from a separate SQL reimplementation. `_load_contracts`' bespoke period math
   and `_get_blocked_map`'s bespoke period math are replaced by the model's values.
2. **One table per section, all non-inactive.** Each ACCUMULATOR and DECUMULATOR section is a
   single table listing every contract with `status != 'inactive'` for that bank (active + DONE +
   KO), ordered by currency priority, bank priority, then stock code — matching term-sheet.
3. **Columns match term-sheet**, in this order:
   `Stock (GTD) | Code | Shares/Day | Spot | Strike | K/O | Start | End | Received | Remaining |
   Total | Next Date | Contract No. | Reference`, then the existing **2-week Closing-Price grid**
   appended after Reference (see Open defaults).
   - `Contract No.` = `bank_doc` (the current "Bank Reference" column, relabeled and moved).
   - `Reference` = `StockContract.reference` (new column).
   - `Received / Remaining / Total` = the model's month values (frequency-adjusted; e.g. 9.5 / 3.5
     / 13.0), replacing ltv-stocks' `tenor × frequency` formula — so they match term-sheet exactly.
4. **Next Date** shows `DONE` (all periods received), `KO` (`status == 'KO'`), else the next
   working-day date — taken from the model.
5. **Positions blocked shares** are the model's `remaining_shares` for active DECUs (fixes the
   zeroed Blocked/Unblocked figures in the Positions section).
6. **GTD suffix** on the stock name, using term-sheet's rule (`No` → "… No GTD"; `Yes` → "… GTD
   1m"; else "… GTD {gtd}"; empty → plain).
7. **KO rows are visually marked** in the Excel (fill highlight) and show `KO` in Next Date, as
   term-sheet does.

### Open defaults (flagged for the reviewer — flip any)

- **Closing-Price grid kept.** The Excel's existing 2-week closing-price columns (which term-sheet
  lacks) are **retained**, appended after the Reference column. *(Alt: drop them for exact
  term-sheet parity.)*
- **Active-count cell kept.** The small count above each section keeps counting **genuinely-active**
  contracts (not DONE, not KO), unchanged. *(Alt: drop it — term-sheet has no such count.)*
- **KO highlight color:** a light red fill on KO rows (mirrors term-sheet's
  `rgba(254,202,202)`), rendered as a solid openpyxl fill.

### Out of scope

- The web view (`/ltv-stocks/`) stays download-only; no on-page tables.
- No change to `ltv_app/blueprints/term_sheet/` — it is consumed read-only, not modified.
- No schema/data changes. `legacy_excel_generator.py` (unused) untouched.

## Affected code & access policy

- **Modified — data layer:** `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` — `_load_contracts`
  (def ~line 58), `_get_blocked_map` (~225), `get_ltv_stocks_full` (~14); delete `_parse_trade_date`
  (~50); add module-level `_stock_name_with_gtd`.
- **Modified — Excel renderer:** `ltv_app/blueprints/ltv_stocks/views.py` — `_xl_contracts`
  (columns/rows). `_generate_excel`, `_xl_positions`, and `_active_count` are otherwise unchanged
  (Positions now receives correct blocked shares from the data layer).
- **Reused, not modified:** `ltv_app/blueprints/term_sheet/models.py:StockContract` (dataclass
  line 40; `__post_init__` line 63; `as_dict` line 203; `summary` / GTD rule lines 140–149).
- **Display reference:** `ltv_app/blueprints/term_sheet/pages/term_sheet/home.html`.
- **Tables (read-only):** `tbl_stock_contract`, `tbl_stock_contract_period`, `tbl_bank_account`,
  `tbl_code`, `tbl_currency`, `tbl_stock_price`.
- **Routes** (in `ltv_app/blueprints/ltv_stocks/views.py`), unchanged by this spec: `home`
  (`/ltv-stocks/`, GET/POST) and `download` (`/ltv-stocks/download`, POST). Both `@login_required`,
  accessible to **all authenticated levels (1=admin … 5=viewer)**, read-only; unauthenticated
  requests redirect to the login page (Flask-Login). No `@superuser_required`; no new routes.

## Design

Two files change: the data layer `ltv_app/blueprints/ltv_stocks/create_ltv_stocks.py` and the Excel
renderer `ltv_app/blueprints/ltv_stocks/views.py`. `term_sheet/models.py` is imported, not edited.

### Data layer — `create_ltv_stocks.py`

- Import `StockContract` from `ltv_app.blueprints.term_sheet.models`.
- Replace `_load_contracts(db, result, price_map)` internals: select the ordered `ref_num`s of all
  non-inactive contracts (join `tbl_bank_account` / `tbl_code` / `tbl_currency` for ordering and
  the ccy/bank grouping keys), and for each, build a `StockContract(db=db)`, call `.get(ref_num=…)`
  (runs `__post_init__`), then assemble the contract dict from the instance's computed attributes:
  - `stock_name` = `_stock_name_with_gtd(sc.stock_name, sc.gtd)`
  - `code`, `bank_doc`, `reference` = `sc.code`, `sc.bank_doc`, `sc.reference`
  - `shares_day` = `f"{sc.daily_shares:,.0f} / {sc.daily_shares*2:,.0f}"` if leveraged else single
  - raw `spot`/`strike`/`ko` from `sc.spot`, `sc.spot*sc.strike_rate/100`, `sc.spot*sc.ko_rate/100`
  - `start_date_raw`, `last_end_date_raw` parsed from `sc.start_date`, `sc.end_date`
  - `received`, `remaining`, `total` = `sc.received_periods`, `sc.remaining_periods`,
    `sc.total_periods` (months)
  - `is_ko` = `sc.status == 'KO'`; `is_done` = `sc.next_date == 'DONE'`
  - `next_date_display` = `'DONE'` if is_done else `'KO'` if is_ko else formatted `sc.next_date`
  - `closing` from `price_map.get(sc.code_ref)`
  - group into `result[sc.ccy_id][sc.bank_id]['accu'|'decu']` (key on `sc.transaction_type`), using
    `sc.bank_name` / bank `report_label` / priority read alongside the ordering query.
- Keep the module-level helper `_stock_name_with_gtd(stock_name, gtd)` (term-sheet's rule).
- Replace `_get_blocked_map` internals: for each non-inactive DECU, use the `StockContract`
  instance's `remaining_shares` as the blocked amount, keyed `(sc.bank_id, sc.code)`; skip when 0.
- `get_ltv_stocks_full` calls `_load_contracts(db, result, price_map)` (no `report_date`); the
  current-week filter and `_parse_trade_date` are removed.

### Excel renderer — `views.py` `_xl_contracts`

- Reorder/relabel the fixed columns to the term-sheet set (Req 3): `Stock Name, Code, Shares/Day,
  Spot Price, Strike Price, K/O Price, Start Date, End Date, Received, Remaining, Total, Next Date,
  Contract No., Reference`, then the Closing-Price grid.
- Write `Received/Remaining/Total` from the month values (number format `0.0`), `Next Date` from
  `next_date_display` (string `DONE`/`KO` or a `d-mmm-yy` date), `Contract No.` from `bank_doc`,
  `Reference` from `reference`.
- Apply the KO fill to a row when its `is_ko` is true.
- `_active_count` and the count cell are unchanged (Open default).

### Edge cases

- **Contract with no period rows:** `StockContract.__post_init__` only assigns `next_date` inside
  the period loop, so a period-less contract leaves `next_date` unset → `as_dict()` raises
  `AttributeError`. The loader wraps each per-contract build in `try/except AttributeError` and
  **skips** such contracts (a contract with no schedule is not displayable), continuing the loop.
- **Unrecognized `frequency`:** `StockContract` raises `KeyError` for a frequency not in
  {`monthly`, `bi-monthly`, `bi-weekly`, `weekly`}. This is pre-existing model behavior shared with
  the term-sheet page; the loader adds no new handling (parity with term-sheet).
- **`gtd` NULL/empty:** `_stock_name_with_gtd` returns the plain stock name.
- **No non-inactive contracts for a bank:** `_xl_contracts` renders its existing "No … contracts."
  row — unchanged.
- **Missing closing price** for a code/date: the cell is left blank (existing behavior).
- Read-only (SELECT only); no INSERT/UPDATE, so no write-error handling is introduced.

## Convention compliance (CLAUDE.md)

- **No schema/data changes** → no `localhost/` impact analysis required.
- **DB access** uses the connection passed from `get_db()`; `StockContract` uses that same
  connection. No direct `sqlite3.connect()` in application code.
- **Timezone:** the report date originates from `ph_today()` in
  `ltv_app/blueprints/ltv_stocks/views.py:home`; neither the loader nor `StockContract` calls
  `datetime.now()` (only `datetime.strptime` on stored dates).
- **Positions numbers change:** blocked/unblocked values change (now correct). Explicitly approved
  by the user.
- **Excel templating:** the LTV Stocks Excel is generated template-free (`Workbook()` in
  `views.py`) — a pre-existing deviation from the `instance/excel_templates/` convention. This spec
  edits that generator's columns but intentionally does **not** convert it to a template (a large,
  separate effort). Flagged; out of scope.

## Testing

File: `tests/functional/test_ltv_stocks_active_count.py` (rework — the old filter/count tests are
replaced since the mechanism changed).

- `test_load_contracts_matches_stockcontract`: seed a contract with a known schedule (some periods
  received, some not) and assert the loaded record's `received`/`remaining`/`total`, `is_done`,
  `is_ko`, and `next_date_display` equal what `StockContract(...).as_dict()` returns for the same
  contract.
- `test_active_and_ko_and_done_all_listed`: an active, a DONE, and a KO contract are all present in
  the section (no week filter).
- `test_next_date_done_ko_date`: DONE → `'DONE'`; KO (`status='KO'`) → `'KO'`; partially-received →
  a date string.
- `test_blocked_map_uses_remaining_shares`: a DECU with unreceived periods yields blocked shares
  equal to the model's `remaining_shares` (was 0 before).
- `test_stock_name_gtd_suffix`: `_stock_name_with_gtd` → `"X No GTD"`, `"X GTD 1m"` (Yes),
  `"X GTD 3m"` (3m), `"X"` (empty/None).
- `test_generate_excel_has_reference_and_contract_no_columns`: `_generate_excel` output sheet has
  `Reference` and `Contract No.` headers, and a KO row is filled.

## Verification

1. Unit tests above (real temp SQLite).
2. Live spot check: download the report for `2026-07-06`; on the DBPe sheet confirm the ACCU table
   lists Alibaba-6/7, China Molybdenum-19, Geely-14, HK Exchange-18, Tencent-8/10 with GTD names,
   Received/Remaining/Total and Next Date **matching `/term-sheet/DBPe`** (e.g. Alibaba-6 = 9.5 /
   3.5 / 13.0), the Reference/Contract No. columns populated, KO rows highlighted, and the Positions
   section showing non-zero Blocked shares for active DECUs.
