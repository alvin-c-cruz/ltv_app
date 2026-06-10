# Unified Average Engine + Printable Trades Done Report

**Date:** 2026-06-10
**Status:** Approved

## Goals

1. **Unification (incremental):** one shared cost/average calculation engine,
   applied this session ONLY to the New Trades Done report. The index page,
   `get_balance`, and the bank transactions page keep their own copies for now
   and migrate later.
2. **Printable popup:** an HTML page equivalent to the New Trades Done Excel
   file so the user can print directly from the browser. The Excel download
   remains unchanged and stays in the toolbar.

## Part A — Engine

- New pure function `accumulate_position(transactions)` in
  `ltv_app/blueprints/transactions/models.py`: the weighted-average cost loop
  (currently duplicated in 4 places) extracted verbatim. Takes an ordered
  iterable of rows with `quantity`, `price`, `brokerage`, `commission`,
  `foreign_charge`, `stamp_duty`, `misc`. Returns
  `(balance, cost_to_date, last_average)` where `last_average` is the most
  recent non-zero average (cost basis when a position is sold out).
- `trades_done_average.py` refactor: keeps its SQL (transactions up to the
  report trade_date, ordered by the bank's transaction_basis) and its rule of
  skipping Transfers dated on the report date (now a pre-filter), then calls
  the engine. `average = cost_to_date / balance` when balance > 0, else
  `last_average`. **Numbers identical to today.**
- Unit tests (`tests/unit/test_accumulate_position.py`): buys produce weighted
  average including charges, sells leave the average unchanged, transfer-out
  reduces cost proportionally, sold-out → last_average preserved, short
  positions carry zero cost, re-buy after flat restarts the average.

## Part B — Printable report

- New route `GET /trades/print_with_gain_loss/<trade_date>` (`@login_required`).
  Empty date → flash "No data to print." and redirect to the Trades page
  (mirrors the download routes).
- New extension `ltv_app/blueprints/transactions/extensions/trades_done_report.py`
  (`TradesDoneReport`): builds plain dicts mirroring the Excel writer —
  - ACCU and DECU sections from `trade_summary.accus/decus` (bank, stock,
    shares, spot, strike, KO, tenor, GTD — the preformatted dataclass fields).
  - Transaction blocks per currency/type (Transfers skipped): rows with price,
    shares, amount; **Average** on the last row of each stock per bank for Buy
    blocks; **Cost / Gain-Loss / %** computed in Python via `TradesDoneAverage`
    **only for Sell (Spot)** rows (cost = qty x average, gain = amount - cost,
    pct = gain/cost, guarded for cost = 0).
  - Per-bank Sell (Spot) subtotals (proceeds, cost, gain/loss, pct) and a
    block TOTAL (shares, amount) when a block has multiple banks or a stock
    has multiple trades — same conditions as the Excel writer.
  - Block gain/loss header label: "Gain" / "Loss" / "Gain / Loss" + ccy from
    the signs of the block's gain values (replicates the Excel COUNTIF header).
- Standalone template `print_trades_done.html` (does NOT extend base.html —
  no navbar): clean tables styled for paper, a "Print" button calling
  `window.print()` wrapped in a `no-print` class hidden by `@media print`.
- Toolbar button "Print Trades Done" on the Trades Done page, `target="_blank"`
  (the popup), next to the existing download buttons which remain unchanged.

## Testing

- Unit tests for the engine (no DB).
- Existing download tests keep passing with identical averages (regression on
  Part A).
- New functional tests for the print route: login required; empty date
  redirects with flash; Buy-only page shows Average but no Cost/Gain-Loss
  cells; prior-buy + Sell (Spot) shows computed cost/gain values; Sell (Short)
  shows no gain/loss cells.

## Out of scope

- Migrating `gather_position_bulk`, `get_balance`, `_compute_transactions` to
  the engine (later sessions).
- Any change to the Excel download routes/files.
