# LTV Stocks — Feature Status

**Location:** `ltv_app/blueprints/ltv_stocks/`
**Route:** `/ltv-stocks/`
**Last reviewed:** 2026-07-06
**Overall stage:** 🚧 Active development — Excel report functional; web view is download-only.

This document tracks the current state of the LTV Stocks report so progress can be
monitored across development sessions. Update the status markers and changelog as work lands.

Legend: ✅ done & tested · 🟡 done, thin/no tests · 🚧 in progress · ⬜ not started · ⚠️ tech debt / risk

---

## 1. What this feature does

Generates the **LTV Stocks report** — a per-bank, per-currency summary of derivative
contracts (ACCU / DECU accumulators & decumulators), the resulting stock positions, and a
two-week grid of closing prices. It is the modern (`ltv_app`) re-implementation of the legacy
`localhost/modules/ltv_stocks2.py` report.

The report exists in two surfaces:

| Surface | Route | Entry point | Content today |
|---|---|---|---|
| Web page | `GET/POST /ltv-stocks/` | `views.home` → `get_ltv_stocks` | **Date picker + Download button only** — no tables rendered |
| Excel download | `POST /ltv-stocks/download` | `views.download` → `get_ltv_stocks_full` → `_generate_excel` | Full ACCU/DECU + positions + closing-price grid |

---

## 2. Architecture & data flow

```
views.home  ──► get_ltv_stocks(db, report_date)          # positions + weekly txns only
                  ├─ _load_closing_prices                 # latest close ≤ report_date
                  ├─ _load_positions                      # net balances, blocked/unblocked, avg, %chg
                  └─ _load_transactions                   # this-week txn strings → positions
                     └─ renders home.html (form only; `data` just toggles the Download button)

views.download ──► get_ltv_stocks_full(db, report_date)  # contracts + positions + 2-week prices
                  ├─ _load_closing_prices
                  ├─ _load_contracts                      # ACCU/DECU, tenor/periods, DONE/KO, week filter
                  ├─ _load_positions
                  ├─ _load_transactions
                  ├─ _get_two_week_dates                  # prev full week + current week (10 dates)
                  └─ _load_closing_prices_multi           # {code_ref: {date: price}}
                     └─ _generate_excel                   # one sheet per bank-ccy
                          ├─ _xl_contracts (ACCUMULATOR)  # active count + table + closing grid
                          ├─ _xl_contracts (DECUMULATOR)
                          └─ _xl_positions
```

### Files

| File | Lines | Role | Status |
|---|---|---|---|
| `views.py` | ~307 | Routes + full Excel generator (`_generate_excel`, `_xl_contracts`, `_xl_positions`, `_active_count`) | 🟡 |
| `create_ltv_stocks.py` | ~381 | Data layer — all SQL and business rules | 🟡 |
| `pages/ltv_stocks/home.html` | ~22 | Web template (form only) | 🚧 |
| `__init__.py` | 1 | Blueprint export | ✅ |
| `extensions/legacy_excel_generator.py` | ~321 | **Dead code** — not imported anywhere | ⚠️ |
| `views_modern_backup.py` | ~277 | **Dead code** — not imported anywhere | ⚠️ |

---

## 3. Business rules implemented

| Rule | Where | Status |
|---|---|---|
| **Active** = not DONE and not KO | `_load_contracts` | ✅ |
| **DONE** = all periods received (`remaining == 0`) and not KO | `_load_contracts` | ✅ |
| **KO** = stored `status == 'KO'` (no price-based detection); KO overrides DONE and keeps a next-month date | `_load_contracts` | ✅ |
| Active-count cell = **plain integer** excluding DONE & KO (not an Excel formula) | `_active_count` / `_xl_contracts` | ✅ |
| DONE/KO contracts listed **only if `trade_date` in current week** (Mon–Fri of report date); Active always listed; missing/unparseable date ⇒ omit | `_load_contracts` | ✅ |
| **Blocked shares** = DECU remaining periods × shares/day (×2 if leveraged) | `_get_blocked_map` | 🟡 |
| **Positions**: net qty ≠ 0; `unblocked = balance − blocked`; `avg = buy_cost / bought`; `%chg = close/avg − 1` | `_load_positions` | 🟡 |
| Weekly transaction strings (Mon→report_date) appended per position | `_load_transactions` | 🟡 |
| Two-week closing grid: previous full week (Mon–Fri) + current week, 10 dated columns | `_get_two_week_dates` | 🟡 |
| Tenor parsing (`'12m'` → 12), bi-monthly frequency doubles periods | `_parse_tenor_*` | 🟡 |
| Per-stock header colors, ACCU/DECU section styling, landscape A4 | `_xl_contracts` | 🟡 |
| `report_label` overrides `bank_name` in sheet header | `_generate_excel` | 🟡 |

---

## 4. Test coverage

**File:** `tests/functional/test_ltv_stocks_active_count.py` — **6 tests, all passing.**

| Test | Covers |
|---|---|
| `test_load_contracts_sets_is_ko` | `is_ko` flag; KO keeps a next-month date |
| `test_ko_overrides_done_when_all_periods_received` | KO overrides DONE even when fully received |
| `test_active_count_excludes_done_and_ko` | `_active_count` pure logic |
| `test_generate_excel_count_is_plain_integer` | A3 count cell is a plain `int`, not a formula |
| `test_current_week_filters_done_and_ko` | Active always listed; DONE/KO only in current week |
| `test_missing_trade_date_done_ko_omitted` | NULL `trade_date` on DONE/KO ⇒ omitted |

### Coverage gaps ⬜

- `_load_positions` — balances, blocked/unblocked, average cost, `%chg` (**untested**)
- `_get_blocked_map` — DECU blocked-share math, leveraged ×2 (**untested**)
- `_load_transactions` — weekly txn string formatting / attachment (**untested**)
- `_load_closing_prices` / `_load_closing_prices_multi` — latest-price selection (**untested**)
- `_get_two_week_dates` — the 10-date window edges (**untested**)
- `_xl_positions` and the contracts closing-price grid — structure/values (**untested**)
- End-to-end `download` route (HTTP 200, XLSX bytes) and `home` route (**untested**)

---

## 5. Known gaps, decisions & risks

- 🚧 **Web view renders no data.** `home()` computes positions + weekly transactions but the
  template only uses the result to toggle the Download button. If an on-page table is a goal,
  it is not started. *(Confirm whether this is intentional — download-only — or a planned gap.)*
- 🟡 **`next_date` ("Date of Next Mo.", column M) is an approximation** — `last_end_date + 30 days`
  (`_next_month_date`), not a calendar/holiday-aware next period.
- 🟡 **KO is status-only.** No price-vs-KO-barrier detection; relies on `tbl_stock_contract.status`
  being set to `'KO'` upstream.
- ⚠️ **Two dead files** (`legacy_excel_generator.py`, `views_modern_backup.py`, ~600 lines total)
  are not imported anywhere. Candidates for deletion once confirmed obsolete.
- 🟡 **Average cost** uses lifetime buy cost ÷ lifetime bought shares (not FIFO / not net of sells).

---

## 6. Data model dependencies (read-only)

- `tbl_stock_contract` (`transaction_type` ACCU/DECU, `daily_shares`, `leveraged`, `spot`,
  `strike_rate`, `ko_rate`, `tenor`, `frequency`, `status`, `trade_date`, `start_date`, `bank_doc`)
- `tbl_stock_contract_period` (period rows → received count, `MAX(end_date)`)
- `tbl_transaction` (positions, weekly transactions, average cost)
- `tbl_stock_price` (`closing_price` by `trade_date`)
- `tbl_bank_account` (`bank_id`, `report_label`, `priority`), `tbl_code`, `tbl_currency`, `tbl_transaction_type`

The feature is **read-only** — no writes, no schema changes.

---

## 7. Recent changelog (git)

| Commit | Summary |
|---|---|
| `d220f38` | List DONE/KO contracts only when traded in the current week |
| `21e83a1` | KO status overrides period-based DONE |
| `ab8ab20` | Count active contracts excluding DONE and KO as a plain integer |
| `ab1bfa9` | Expose `is_ko` flag on report contracts |
| `969180a` | Improve LTV Stocks Excel report with legacy features (Phase 1) |
| `3f9d39b` | Include term sheets with KO status |
| `25e4fbb` | Initial LTV stocks report |

**Design/plan docs:**
`docs/superpowers/specs/2026-07-02-ltv-stocks-current-week-done-ko-filter-design.md`,
`docs/superpowers/plans/2026-07-02-ltv-stocks-active-count-ko.md`,
`docs/superpowers/plans/2026-07-02-ltv-stocks-current-week-done-ko-filter.md`.

---

## 8. Suggested backlog (proposed — not committed)

- ⬜ Decide web view direction: render positions/contracts on-page, or keep download-only.
- ⬜ Add tests for the positions / blocked-shares / weekly-transactions / price paths.
- ⬜ Delete or archive the two dead files after confirmation.
- ⬜ Revisit `next_date` approximation vs. a real next-period date.
- ⬜ Consider a project skill to standardize LTV Stocks development (see note below).
