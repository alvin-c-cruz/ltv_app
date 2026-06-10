# Transfer Modal — Auto-fill Unrounded Average Price + Balance Warning

**Date:** 2026-06-10
**Status:** Approved

## Requirements (user)

- In the Add Transfer modal, the Price field should auto-fill with the From
  account's average cost of the selected stock — **unrounded** (full float,
  like historical transfer rows e.g. `12.2262410098598`).
- The average must be computed **as of the modal's Trade Date**.
- The user must be **notified when the From account holds insufficient shares**
  for the quantity being transferred (warning, not a hard block).

## Design

### Endpoint

`GET /trades/average_price/<int:bank_ref>/<int:code_ref>?trade_date=YYYY-MM-DD`
(`@login_required`), in `transactions/views.py`:

- Resolves `code` and `bank_id`, 404 if either ref is unknown.
- `trade_date` defaults to today (ph_today) when missing.
- Uses `TradesDoneAverage` (transactions with `trade_date <= ?` ordered by the
  bank's transaction basis, same-day Transfers excluded — so the transfer being
  entered never feeds its own price), which is extended to also expose
  `self.balance` from the same `accumulate_position` run.
- Returns JSON `{"average": <float or null>, "balance": <float>}` — raw floats,
  no rounding (JSON serializes full double precision).

### Modal wiring (`pages/transactions/home.html`)

- A warning `<div id="transferBalanceWarning">` (red, hidden by default,
  spanning both grid columns) inside the transfer form.
- JS in the existing script block:
  - `updateTransferAverage()` — when Trade Date, From Account, and Stock are
    all set, fetch the endpoint; write `average` into the Price input verbatim
    (empty when null); cache `balance`; re-run the quantity check.
  - `checkTransferQuantity()` — on quantity input, if `abs(quantity) > balance`
    show the warning with the held share count and trade date; hide otherwise.
  - Triggers: `change` on the modal's trade_date/bank_ref/code_ref, `input` on
    quantity.

### Tests (`tests/functional/test_average_price.py`)

- Requires login (302 → /login).
- Unknown bank/code refs → 404.
- Two buys (1000 @ 10 + 500 @ 11) → `average == 15500/1500` exactly
  (unrounded float equality) and `balance == 1500`.
- Date cutoff: buy on an early date, buy later; query with the early date →
  average/balance include only the first buy.
- No holdings → `average` null, `balance` 0.

## Out of scope

- Blocking the Save on insufficient shares (warning only).
- Same auto-fill for other modals (Spot/Dividends).
