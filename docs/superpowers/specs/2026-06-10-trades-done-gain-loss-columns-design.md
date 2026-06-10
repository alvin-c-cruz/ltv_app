# New Trades Done — Gain/Loss Columns Only for Sell (Spot)

**Date:** 2026-06-10
**Status:** Approved

## Problem

The New Trades Done export (`/trades/download_with_gain_loss/<date>`,
built by `ltv_app/blueprints/transactions/extensions/download_trades_done_with_gain_loss.py`)
writes the gain/loss columns on every transaction row:

- Detail rows: `L` (`=G*O` cost), `M` (`=H-L`), `N` (`=M/L`) are added to the
  `cols` dict unconditionally (only their number formats are gated on Sell).
- Block headers: after each transaction-type block, `M`/`N` header cells are
  overwritten with the "Gain / Loss" formula headers unconditionally — so even
  BUY blocks show them (seen in the uploaded sample: M5/N5 on a Buy-only sheet).

## Requirement (user decision)

Columns L/M/N (and the hidden `O` average that feeds them, the M/N formula
headers, and the per-bank L/M/N subtotals) appear **only for `Sell (Spot)`**
blocks. All other types — `Buy (Spot)`, `Buy (Pay Short)`, `Sell (Short)`,
`Stock Dividend` — get none of them. Buy types keep their `J` Average column.

## Changes (single file: `download_trades_done_with_gain_loss.py`, `write_transactions`)

1. Block header: write `L`/`M`/`N` labels only when `transaction_type == "Sell (Spot)"`.
2. Detail rows: remove `L`/`M`/`N` from the base `cols` dict; add them together
   with `O` (average) only when `transaction_type == "Sell (Spot)"`.
3. Per-bank cost subtotals: gate `if "Sell" in transaction_type` → `if transaction_type == "Sell (Spot)"`.
4. Gain/Loss header fix-up (M/N at block start): gate on `transaction_type == "Sell (Spot)"`.

## Testing

Extend `tests/functional/test_download_trades_done.py`: download the report and
parse it with openpyxl —

- Buy (Spot) only → columns L, M, N completely empty (no values, no headers).
- Sell (Short) only → columns L, M, N completely empty.
- Prior buy + Sell (Spot) → L/M/N present on the sell block (header + formulas).
- Existing tests keep passing.
