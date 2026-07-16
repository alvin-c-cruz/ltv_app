# Decumulator / Accumulator Period-Schedule Fix — Design

**Date:** 2026-07-16
**Status:** Approved design, ready for implementation plan
**Area:** `term_sheet` blueprint — `CreateSchedules` in `ltv_app/blueprints/term_sheet/models.py`
**Tracks:** BUGS.md — "2026-07-13 — Decumulator period schedule drifts from the bank's trading-day schedule" (Severity: High)

## Problem

The auto-generated **bi-weekly** period schedule for Decumulator/Accumulator contracts
diverges from the counterparty bank's binding termsheet SCHEDULE table. Confirmed on
three DBPe contracts (#1449 Alibaba, #1444 Tencent, #1441 Kuaishou), each corrected by
hand this month. The generator (`CreateSchedules`) **is** holiday-aware (it queries
`tbl_holiday` and rolls off weekends/holidays), so the original "naive calendar loop"
hypothesis in BUGS.md is wrong. There are two distinct root causes, both in the
**bi-weekly / weekly** path only (the `monthly` branch was already patched separately):

1. **Cascading drift** — `__next_end_date` (models.py ~376) computes the next period end
   as `previous_end_date + 14 days`, where `previous_end_date` is the *already
   holiday/weekend-adjusted* end of the prior period. Any forward roll therefore
   permanently shifts every later period (the `+14` is measured from the rolled date,
   not a fixed grid). This is the "one-day-per-period cascade from period 8" seen in
   #1449.
2. **Dropped final period** — the main loop saves a period only while
   `end_date < self.end_date` for non-monthly frequencies (models.py ~316), so the
   terminal period (whose end reaches the tenor maturity) is never written. The schedule
   ends one full period short (#1449/#1444/#1441 all missing period 26).

## Decision

**Approach A — fix the generator so it reproduces the bank's schedule exactly**, with no
manual cross-check needed (chosen 2026-07-16). A **single convention** is assumed to
govern all counterparties (DB / EBSI-SHK / Nomura) per the user; the code is structured
so a per-bank rule could be slotted in later if an EBSI/Nomura schedule ever mismatches.
Rejected alternatives: rewriting the whole engine (re-risks the working monthly fix), and
a post-generation "repair" pass (leaves the root cause in place).

## The corrected convention (reverse-engineered from contract #1449)

The bank's **bi-weekly** rule, verified against #1449's 26-row corrected schedule:

- **Period-end grid** is fixed and anchored at `start_date`:
  `end_i = start_date + (14 · i − 1) calendar days`, `i = 1..N`. Ends land on the same
  weekday each fortnight (Mondays for #1449).
- **Each `end_i` is rolled forward independently** to the next business day (Following
  Business Day convention) — and the **next period returns to the pure grid** (no
  cascade). In #1449 the only rolls were P7 (Mon 2026-10-19 → Tue, +1), P15
  (Mon 2027-02-08 → Wed, +2, Lunar New Year) and P19 (Mon 2027-04-05 → Tue, +1); P8/P16/P20
  all snapped straight back to the grid (diff 0).
- **Period start** = previous rolled end + 1 business day → fully contiguous, no gaps.
- **Period count `N`** covers the tenor: 12m bi-weekly → **26** periods
  (26 × 14 = 364 days ≈ 1 year). General rule: `N = round(tenor_days / step)` where
  `step` = 14 (bi-weekly/bi-monthly) or 7 (weekly) and `tenor_days = (start_date + tenor
  months) − start_date`.

Weekly is the same with `step = 7`. `monthly` is out of scope (unchanged).

## Code change

Single file: **`ltv_app/blueprints/term_sheet/models.py`**, class `CreateSchedules`.

- Rewrite the **bi-weekly / bi-monthly / weekly** branch of `__next_end_date` so each
  period end is derived from the **fixed anchor** (`start_date + step·i − 1`), rolled
  once via the existing `check_date`, instead of `previous_end_date + step`.
- Replace the `while end_date < self.end_date` main loop with an explicit **N-period**
  iteration (N computed from tenor/step as above) so the terminal period is written.
- `start_i` stays `previous_rolled_end + 1` via the existing `__next_start_date`; per-period
  business-day counting stays via the existing `Counter`.
- **Do not touch** the `monthly` branch (keeps the Feb-29/end-of-month fix intact) or
  `check_date` / `Counter` / `is_holiday` (holiday awareness is correct).

## Verification / acceptance

- A **regression harness** regenerates the schedules for **#1449, #1444, #1441** from
  their stored contract fields (trade/start date, tenor, frequency) against the same
  holiday table, and asserts **zero diff** — period-by-period `start_date`, `end_date`,
  `days` — versus each contract's **corrected** `tbl_stock_contract_period` rows (which
  already match the bank termsheets). "Reproduces exactly" = zero diff on all three.
- Run against the production DB snapshot (has the corrected schedules + `tbl_holiday`),
  not production.

## Scope / non-goals

- **Forward-looking + on-demand** only: affects new contract creation and the "Refresh
  Periods" action. Existing locked contracts' stored schedules are **not** rewritten.
- `monthly` frequency unchanged.
- Single convention for all counterparties now; per-bank rules deferred until evidence of
  divergence (all current evidence is DBPe).

## Risks / open questions

- The forward-roll depends on `tbl_holiday` being complete for the underlying's currency.
  A missing HK holiday would make a generated end differ from the bank's by a day. The
  regression harness catches this for the three known contracts; a broader holiday-data
  audit is out of scope here.
- `N = round(tenor_days / step)` should be validated for non-12m tenors and month-end
  start dates during implementation (add those as harness cases if any such contract
  exists).
