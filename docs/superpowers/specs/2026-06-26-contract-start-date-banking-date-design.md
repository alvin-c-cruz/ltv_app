# Contract Start Date → Banking Date (currency-aware)

**Date:** 2026-06-26
**Status:** Approved design, pending implementation plan
**Scope:** Front-end only change to the "Add Contract" modal on the Trades Done page.

## Problem

On the Trades Done page (`/trades/`), the **+ Contract** modal (Add Accumulator /
Decumulator) auto-fills the **Start Date** field as **Trade Date + 1 calendar day**.
This is computed naively in JavaScript and ignores weekends and market holidays.

The Start Date is the contract's **banking date** and must be the next valid
business day, accounting for the holidays of the **currency tied to the selected
stock** (a stock's currency comes from `tbl_code.ccy_ref`, and holidays are stored
per currency in `tbl_holiday.ccy_ref`).

## Goal

When adding a contract, **Start Date = the next banking day strictly after the
Trade Date**, skipping:

- Saturdays and Sundays, and
- holidays of the selected stock's currency.

The field must recompute whenever the Trade Date or the selected stock changes.

## Decisions (from brainstorming)

1. **Rule:** Next banking day *strictly after* Trade Date (T+1 banking). If
   Trade Date + 1 lands on a weekend/holiday, roll forward to the next banking day.
2. **Scope:** **Add Contract modal only.** The Edit Contract modal keeps its saved
   Start Date untouched (no silent changes to historical records).
3. **No backend or schema changes.** Reuse the existing currency-aware endpoint.

## Approach — front-end reuse only

The currency-aware "next banking day" logic already exists and is already used by
the Spot/Short modals for their value-date fields:

- **Endpoint:** `GET /trades/api/next-banking-day?code_ref=<id>&trade_date=<YYYY-MM-DD>&days=<n>`
  — `ltv_app/blueprints/transactions/views.py:782` (`next_banking_day`). It looks up
  the stock's `ccy_ref`, loads that currency's holidays, and advances `days` banking
  days skipping weekends + those holidays. Returns `{"value_date": "YYYY-MM-DD"}`.
- **Existing front-end pattern:** `updateValueDate(modal)` in
  `ltv_app/blueprints/transactions/pages/transactions/home.html` (~line 733) calls
  the endpoint with `days=2` and writes the result into `.modal-value-date`.

### Changes (all in `home.html`)

1. **Add `updateStartDate(modal)`** mirroring `updateValueDate()`:
   - Read `code_ref` (stock `<select>`) and `trade_date` from the modal.
   - If a stock is selected → `fetch('/trades/api/next-banking-day?code_ref=…&trade_date=…&days=1')`,
     write `data.value_date` into the modal's `.modal-start-date` input.
   - If no stock is selected yet → fall back to weekend-only `addBusinessDays(tradeDate, 1)`
     (existing helper).
   - On fetch error → log to console and leave the fallback value (consistent with
     `updateValueDate`'s `.catch`).

2. **Wire it in `openTxnModal(id)`** for the Add Contract modal:
   - On open, call `updateStartDate(m)` (replacing the current static `_sdStr` fill
     for `.modal-start-date`).
   - Add `change` listeners on the stock `<select>` and the trade-date input that
     call `updateStartDate(m)` (alongside the existing `updateValueDate` wiring).

3. **Leave the naive `_sdStr` calc** only as the no-stock fallback path (or drop it in
   favour of `addBusinessDays`); do not use it as the final value when a stock is chosen.

4. **Edit Contract modal:** unchanged. Its opener does not call `updateStartDate`.

### Server side

No change. `term_sheet/views.py:add()` already stores whatever `start_date` the form
submits into `tbl_stock_contract`.

## Known limitation (flagged, not fixed here)

`tbl_holiday` only has current (2026–2027) holiday data for **HKD** (`ccy_ref=1`).
USD/JPY/AUD/SGD holiday rows end in 2022. So for non-HKD stocks, the Start Date will
skip weekends but may land on an un-recorded market holiday.

This is **identical** to how the existing Spot/Short value-date fields already behave,
so the feature is internally consistent. The real fix — loading current holiday data
for the other currencies — is **out of scope** for this change.

Separately, an audit of the existing 2027 **HKD** holiday rows against the officially
gazetted GovHK list found discrepancies (missing weekday holidays 2027-02-09,
2027-04-05, 2027-10-08; a spurious 2027-02-07 Sunday row). Correcting `tbl_holiday`
data is a **separate, approval-gated data change** and is not part of this front-end
spec.

## Testing

Manual, via the running app (login required), HKD stock unless noted:

1. Trade Date such that Trade+1 is a normal weekday (no holiday) → Start = Trade+1.
2. Trade Date such that Trade+1 is a Saturday → Start rolls to the following Monday
   (or next banking day if Monday is a holiday).
3. Trade Date immediately before a known HK holiday → Start skips the holiday.
4. Change the selected stock after opening → Start Date recomputes.
5. Change the Trade Date after opening → Start Date recomputes.
6. No stock selected → Start Date uses weekend-only fallback (no crash, no hung fetch).
7. Edit Contract modal → saved Start Date is preserved, not overwritten.

## Files touched

- `ltv_app/blueprints/transactions/pages/transactions/home.html` (JavaScript only).
