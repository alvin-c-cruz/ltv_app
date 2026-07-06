# LTV Stocks Report — Exact Native Replica of the Legacy Excel

**Date:** 2026-07-06
**Status:** Approved (design)
**Scope:** `ltv_app/blueprints/ltv_stocks/` (Excel download only)
**Supersedes:** all prior 2026-07-06 ltv-stocks specs/plans and the 2026-07-02 filter/active-count specs.
The authoritative output is the legacy `localhost/create_LTV_Stocks.py` Excel.

## Goal

Make `ltv_app`'s `/ltv-stocks/download` produce a workbook **byte-for-byte equivalent** to the legacy
`localhost/modules/ltv_stocks2.py` output (validated against the golden file
`localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx`), by **porting the legacy calculators
natively** into `ltv_app` — with **no runtime dependency on `localhost/`** — and rebuilding the Excel
writer. Two deliberate omissions (below): the AA–AJ per-day status columns and the off-print-area
helper columns.

The correctness lives in two legacy calculators — `term_sheet.summary_ts_raw` (+ `term_sheet` schedule)
and `transaction_list.blocked_shares`/`stock_position`. The existing `ltv_app`
`create_ltv_stocks.py` and the truncated `extensions/legacy_excel_generator.py` are a **redesign, not a
port**, and diverge in six ways (contract `total`, `received`, `next_date`, DONE, `blocked_shares`,
and the week range). They are replaced.

## Scope decisions

- **Surface:** Excel download only. `/ltv-stocks/` web page stays download-only (date picker + button).
- **Kept exactly:** the printed report area `A1:X{n}` per sheet — ACCU/DECU contract tables and the
  positions table, the empty `closing_price`/`record` helper sheets, the `INDEX/MATCH` price formulas
  (manual-paste workflow retained), hidden columns C (bank_doc) and M (ticker), the count-cell
  `={n}-COUNTIF(N..,"*DONE*")` formula, the cross-sheet `SUM` HKD totals, and the O–X ten-date closing
  grid **including** its grey-fill (pre-start / post-end / holiday) and literal `'Done'` boundary marks.
- **Dropped (open defaults — flip any):**
  1. **AA–AJ** per-day accumulator status columns (explicitly out of scope).
  2. The remaining **off-print-area helper columns** (beyond column X): contract `Z` (leverage flag,
     only fed AA–AJ), contract `AK` (reference), and the position `Y/Z/AA/AB/AC` reconciliation
     formulas (`SUMIF` against the `record` sheet + filename-parsing). These are invisible in the
     printed report and mostly supported AA–AJ / the reconciliation workflow. *(Alt: keep the position
     Y–AC reconciliation if you rely on it.)*
- **No `localhost/` import at runtime.** No schema/data changes.

## The ported calculators (exact algorithms)

### 1. Contract schedule — port of `term_sheet.get_header` / `get_schedule` / `get_footer`

Per contract `ref_num`:
- **Header** from `tbl_stock_contract` (+ joins): `transaction_type, daily_shares, leveraged, spot,
  strike_rate, ko_rate, tenor, frequency, gtd, status, bank_doc, start_date, code, ccy`,
  plus `yahoo_ticker` from `tbl_code`, and the bank's `indicative` from `tbl_bank_account`.
  `strike = round(strike_rate*spot/100, 4)`, `ko = round(ko_rate*spot/100, 4)`.
- **Schedule** from `tbl_stock_contract_period` (no ORDER BY → insertion order), **1-indexed** dict.
  Per period: `end_date` = the row's `end_date`; `start_date` = the contract's `start_date` for
  period 1, else the next working day after the previous period's `end_date`. `days` = the row's
  `days`, or if empty `count_days(start_date, end_date, ccy)` = inclusive count of weekday,
  non-holiday dates. `total_shares = days * daily_shares * (2 if leveraged=='Yes' else 1)`.
  `received` and `gtd` stored raw.

### 2. Contract record — port of `summary_ts_raw`

- **Selection** (per bank, per type): `SELECT ref_num FROM tbl_stock_contract JOIN tbl_bank_account
  WHERE transaction_type = 'ACCU'|'DECU' AND bank_account.ref_num = ? AND status != 'inactive'`
  (keeps active **and** KO; **no ORDER BY** → DB insertion order, grouped by ccy).
- **stock_name GTD suffix:** `gtd in ('Yes','1m')` → `"{name} GTD 1m"`; `'No'` → `"{name} NO GTD"`;
  else strip non-digits from `gtd` → `"{name} GTD {n}m"`.
- **total** = `len(schedule)` if monthly; `len/4` weekly; `len/2` bi-monthly.
- **received** = walk periods 1..last, **break on the first `received == ''`**, adding `+1` monthly /
  `+0.25` weekly / `+0.5` bi-monthly per leading filled period. `next_date` = next working day after
  the first unreceived period's `end_date` (a **datetime**; `''`/none if all filled).
- **remaining** = `total - received`. **DONE** is decided in the writer as `received == total`.
- `shares` string: `"{s:,.0f} / {2s:,.0f}"` if leveraged else `"{s:,.0f}"`. `spot/strike/ko` as
  `"{:,.4f}"` strings. `start_date`/`end_date` kept as **datetime** objects (the writer's O–X date
  comparisons depend on this). `bank_doc`, `yahoo_ticker`, `reference` passed through.

### 3. Positions — port of `stock_position` + `blocked_shares`

Per (bank, code), long leg only, when share balance is non-zero:
- **balance** = the last transaction record's running balance (`ending_balance`).
- **average** = `"={cost_to_date}/{balance}"` (an Excel formula string) when balance non-zero, else the
  last record's running average; recomputed only for codes that traded on the report date.
- **blocked** = over each **active** DECU contract for that code+bank (`status='active'`), sum
  `total_shares` of every period whose `end_date > cutoff`, where `cutoff` = the report date if the
  bank's `indicative == 'YES'` else the previous working day (compared as `YYYY-MM-DD` strings).
  **Cap:** if blocked ≥ balance → `blocked = balance, unblocked = 0`; else `unblocked = balance -
  blocked`. ACCU contracts never block.
- **transactions** narrative for the report date (port of `get_ranged_transactions`).
- Positions are **sorted by code**.

Note the two different filters: contract listing = `status != 'inactive'`; blocked-shares =
`status = 'active'`. Preserve both.

## The Excel writer (port of `ltv_stocks2` `create`/`report_header`/`contract`/`position`)

Rebuild on `ltv_app` openpyxl conventions (self-contained `Workbook()`), reproducing the legacy cells
exactly. Full cell-by-cell mapping is captured in the implementation plan; the essentials:

- **Workbook:** first two sheets `closing_price` and `record` created **empty**. Then one
  `f'{bank}-{ccy}'` sheet per bank × ccy (`['HKD','SGD']`), **skipped** unless it has an ACCU, a DECU,
  or a position. A4 landscape, tight margins, `print_area = 'A1:X{n}'`. Hidden columns C and M.
- **`report_header`:** `A` = `"{BANK NAME} as of {report_date:%B %d, %Y}"` (size 16 bold); `H`='updated';
  `I` = the current-week Monday. Per-bank sub-title fills as in the legacy.
- **Contract table** (ACCU then DECU): count cell `A` = `={n}-COUNTIF(N{first}:N{last},"*DONE*")`;
  three header rows (with the `Strike Price < / > Closing Price = QTYx1/x2` legend and the
  `RCVD/REM/Total mos.` sub-headers and the O–X date headers `m/d`); data rows with columns
  `A`=stock_name(+code fill), `B`=code(`@`), `C`=bank_doc(hidden), `D`=shares, `E`=spot(`#,##0.0000`),
  `F`=strike(bold), `G`=ko, `H`=start(`d-mmm-yy`), `I`=end, `J`=received, `K`=`=L{r}-J{r}`,
  `L`=total, `M`=ticker(hidden), `N`=next_date **or** `"DONE"` (when `received==total`), `O–X`=closing
  grid. Number format for J/K/L is `'0'` (monthly) or `'0.0'` (fractional).
- **O–X closing grid** (10 dates = previous Mon–Fri + current Mon–Fri, built with **`isoweekday()`**:
  `start = report_date - timedelta(days=6+report_date.isoweekday())`): for each date — grey fill
  (`00C0C0C0`) if before contract start, after end, or a holiday; literal `'Done'` (bold) at the
  end-of-contract boundary (Fri-of-week1 = end+3, else end+1, holiday-aware latch); the report-date
  cell = `=INDEX(closing_price!A:C,MATCH(M{r},closing_price!A:A,),3)` (ccy≠USD); other dates = the
  literal `tbl_stock_price` close for that (code, date).
- **Positions table:** headers `UNBLOCKED/BLOCKED/TOTAL SHARES/Ave. Price/% Inc./Dec.`; data rows
  `A`=stock_name, `B`=code, `C`=ticker(hidden), `D`=unblocked, `E`=blocked(merged E:F),
  `G`=`=D{r}+E{r}`(merged G:H), `I`=average, `J`=`=(L{r}/I{r})-1`(`0.00%`, merged J:K),
  `L`=`=INDEX(closing_price!A:C,MATCH(C{r},closing_price!A:A,),3)`(merged L:N), `O`=transactions
  narrative(merged O:X, no border, row height 50). Header `I` (end date) highlighted yellow.
- **Cross-sheet totals:** after all sheets, write `=SUM('{bank}-HKD'!{countcell}, …)` for ACCU and DECU
  into the primary `DBPe-HKD` sheet at the recorded total rows.

## Supporting helpers to build (native, `get_db()`-based)

- **`working_day`** — holiday-aware `next_day` / `previous_day` / `is_holiday` / `count_days`
  against `tbl_holiday` by currency. (`ltv_app` has a partial next-working-day in `term_sheet/models`
  but no `previous_day`.)
- **`stock_price`** — `get_stock_price(code_ref, date)` over `tbl_stock_price` (the pattern already in
  `create_ltv_stocks._load_closing_prices`).
- **`trades_done_average`** — `cost_to_date / balance` (running month-to-date), matching the legacy
  `trades_done_average`.

## Proposed module layout — `ltv_app/blueprints/ltv_stocks/legacy_port/`

- `term_sheet_calc.py` — schedule + `summary_ts_raw` record producer (§1–2).
- `positions_calc.py` — `stock_position` + `blocked_shares` (§3).
- `working_day.py`, `stock_price.py` — supporting helpers.
- `excel_writer.py` — the full writer (contract/position/create/report_header, minus AA–AJ + off-print
  helpers).

`views.py:download` calls the new `excel_writer` and serves the `BytesIO`. The old
`create_ltv_stocks.py` (divergent) and `extensions/legacy_excel_generator.py` (truncated) are removed.

## Access policy

Routes unchanged: `home` (`/ltv-stocks/`, GET/POST) and `download` (`/ltv-stocks/download`, POST) in
`ltv_app/blueprints/ltv_stocks/views.py`, both `@login_required`, all levels 1=admin…5=viewer,
read-only; unauthenticated → login redirect. No new routes.

## Convention compliance (CLAUDE.md)

- Read-only, **no schema/data changes** → no `localhost/` impact analysis required.
- All DB access via `get_db()`; no direct `sqlite3.connect()` in app code.
- Report date defaults from `ph_today()` (`ltv_app/tz.py`); no `datetime.now()`.
- **Positions numbers change** (blocked/unblocked now correct per the legacy algorithm) — approved.
- **Excel templating:** generated template-free (`Workbook()`), matching the legacy which also builds
  the workbook programmatically; the `instance/excel_templates/` convention does not apply here.

## Edge cases

- **Contract with no period rows:** the legacy indexes `schedule[len(schedule)]` and would `KeyError`
  on an empty schedule (1-indexed, no key 0). The port **skips** contracts whose schedule is empty
  (not displayable) rather than raising.
- **Unknown `frequency`** (not `monthly`/`weekly`/`bi-monthly`): the legacy `total`/`received` fall to
  the `else` branch (÷2 / `+0.5`), i.e. treated as bi-monthly. The port preserves this (no new error).
- **All periods filled (`received != ''` throughout):** the received loop never breaks; `next_date`
  stays empty and `received == total`, so column N renders `"DONE"`. Matches legacy.
- **Missing closing price** for a (code, date): the O–X / positions price cell is left blank/None (the
  legacy `get_stock_price` returns nothing). The report-date cell still writes the `INDEX/MATCH`
  formula (ccy≠USD) regardless; USD report-date cells are left `None`.
- **Zero share balance:** the position is omitted (legacy emits only when balance is truthy). Zero
  balance also means no `=cost/bal` division (the running average fallback is used).
- **`tbl_holiday` empty for a currency:** `working_day`/`count_days` then treat every weekday as a
  working day — same as the legacy.
- **Read-only:** SELECT only; no INSERT/UPDATE, so no write-failure handling is introduced.

## Tables read (all read-only)

`tbl_stock_contract`, `tbl_stock_contract_period`, `tbl_bank_account`, `tbl_code`, `tbl_currency`,
`tbl_transaction`, `tbl_stock_price`, `tbl_holiday`.

## Verification

1. **Golden-file test (acceptance):** generate the report for `2026-07-06` via the new writer and
   compare sheet-by-sheet, cell-by-cell (values **and** formulas, number formats) against
   `localhost/excel_files/LTV_Stocks/2026-07-06 LTV Stocks.xlsx`, over the `A1:X` print area of each
   `{bank}-{ccy}` sheet. Differences must be limited to the intentionally-dropped columns (none inside
   `A1:X`). Concretely, DBPe-HKD ACCU must show the 7 contracts with `Alibaba GTD 3m` RCVD=10 / REM
   formula / Total=13, and the DECU/positions blocks must match.
2. Unit tests for each calculator (real temp SQLite): received consecutive-break, total ÷ freq,
   next_date, DONE, blocked-shares cutoff/cap, GTD naming, count_days.
