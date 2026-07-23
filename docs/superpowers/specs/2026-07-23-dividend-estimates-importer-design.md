# Dividend Estimates Importer — design

Date: 2026-07-23
Status: Approved, pending implementation

## Context

`BUGS.md`'s "No automated path from a fetched dividend declaration to an in-app
Estimate row" entry (split out earlier today from the dividends bug-fixes work)
carries a full mapping study against all 97 files in `dividends_analysis/json/`
(outside `server/`, produced by the `dividends-analysis` skill). Key findings that
shape this design:

- One JSON file = one declaration, with an `entitlement[]` array of one entry per
  bank. One file → N `CashDividends` rows, not one row per file.
- None of the JSON's identifiers are the DB's actual foreign keys — `bank_ref`/
  `stock_ref`/`ccy_ref` all need a lookup.
- Three JSON schema generations exist; `entitlement[].bank_id` is an `int` (the
  actual `tbl_bank_account.ref_num`) in the 69 oldest files, and a `str` (the short
  `bank_id` code, needs a lookup) in the 28 newest.
- The JSON's own `already_in_tbl_cash_dividends` flag is **stale/unreliable**:
  `tbl_cash_dividends` currently has exactly 48 rows (all `status='Actual'`), which
  are a perfect 1:1 match to 12 of the JSON files — all still flagged `false`. That
  data was entered independently of the sweep tooling. An importer must check the DB
  directly, not the flag.
- No WHT/tax source in the JSON (skill's own Excel export uses a `0` placeholder);
  no stored "actual HKD credited" field to map `hkd_amount_actual` into (always
  `null` in every file today anyway).

`dividends_analysis/json/` is outside `server/`, gitignored, and not deployed to
PythonAnywhere — this rules out a web route; the importer has to be a local script.

## Scope

Build `server/scripts/import_dividend_estimates.py` — a local, re-runnable,
dry-run-by-default script that reads every file in `dividends_analysis/json/` and:

1. Resolves each entitlement row's bank/stock/currency to the DB's actual foreign
   keys.
2. Checks `tbl_cash_dividends` directly (never the JSON flag) for an existing row.
3. In dry-run (default): reports what it would do, writes nothing.
4. In `--apply`: inserts new rows as `status='Estimate'`, and corrects
   `already_in_tbl_cash_dividends` to `true` in JSON files whose declaration is now
   fully represented in the DB (fixing the 12 known-stale files and staying accurate
   for future sweeps).

Out of scope: pushing any of this to production (production has no `dividends_analysis/`
files and no mechanism to run this script — a separate, later, explicit step if ever
needed), a `--year`/file filter (YAGNI — dry-run already shows everything, 97 small
local files process instantly), promoting Estimate→Actual (existing manual Edit-form
flow already handles that, per the 2026-07-23 dividends bug-fixes work), and any
change to the `dividends-analysis` skill itself or its JSON-writing behavior.

## 1. Lookup resolution

For each JSON file, for each entry in `entitlement[]`:

- **Bank**: if `entitlement[].bank_id` is an `int`, use it directly as
  `tbl_bank_account.ref_num` (Gen A/B files — verified this is literally the
  `ref_num`, not a coincidence, by checking 3 sample values against the DB). If it's
  a `str`, `SELECT ref_num FROM tbl_bank_account WHERE bank_id=?` (Gen C files).
- **Stock**: `SELECT ref_num FROM tbl_code WHERE code=?` using the file's
  top-level `stock_code`.
- **Currency**: `SELECT ref_num FROM tbl_currency WHERE ccy_id=?` using the file's
  top-level `currency` (all 5 currencies seen — `HKD`, `JPY`, `AUD`, `USD`, `SGD` —
  already have a matching row; no gap expected, but handle a miss anyway per Error
  handling below).

## 2. Existing-row check (not the flag)

For each entitlement row, once `bank_ref`/`stock_ref` are resolved:

```sql
SELECT ref_num FROM tbl_cash_dividends
WHERE bank_id = ? AND stock_id = ? AND ex_date = ?
```

A hit means this specific bank's share of this declaration is already recorded —
no insert for that row. A declaration is only eligible for its
`already_in_tbl_cash_dividends` flag to be corrected to `true` when **every** bank
in its `entitlement[]` array has a matching row (partial matches leave the flag
`false`, and only the still-missing banks get inserted).

## 3. Dry-run report

Default mode (no flags). Per declaration, per bank: `[NEW]` (would insert),
`[ALREADY IN DB]` (skip; flags the file if the whole declaration is covered), or
`[SKIPPED: <reason>]` (unresolvable lookup). Ends with totals: entitlement rows
checked, new rows that would be inserted, already-in-DB rows/files whose flag
would be corrected, and skipped rows with reasons. Writes nothing — no DB insert,
no JSON edit.

## 4. `--apply`

Performs exactly what the dry run reported:
- Inserts each `[NEW]` row via `CashDividends(db=db, bank_id=<ref>, stock_id=<ref>,
  ccy_id=<ref>, declaration_date=..., ex_date=..., record_date=...,
  pay_out=<pay_date>, nominal=<entitled_qty>, dividends_per_share=...,
  tax=0, charges=0, status='Estimate').save()`.
- Rewrites the affected JSON file in place: load with `json.load` (preserves key
  order, since Python 3.7+ dicts are ordered and nothing reorders keys), flip
  `already_in_tbl_cash_dividends` to `true`, write back with
  `json.dump(..., indent=2, ensure_ascii=False)` — 2-space indent matches every
  existing file's current formatting exactly, so a `git diff`-style comparison would
  show only the one changed line. Every other file is untouched.

Both writes are gated on `--apply` only — dry-run stays purely read-only.

## Error handling

- Unresolvable bank/stock/currency lookup → skip that one entitlement row, log a
  warning with the file name and the unresolved value, keep processing the rest of
  that file and all other files. Never abort the whole run on one bad row.
- Malformed/unreadable JSON file → skip with a warning, keep going.
- A file with an empty `entitlement[]` → nothing to do for it (none observed in the
  current 97, but handle gracefully rather than assuming it can't happen).

## Verification

No test suite exists in this repo. Verification, matching this session's established
approach:

1. Run dry-run against the real local DB. Confirm the "already in DB" set is exactly
   the 12 files / 48 rows already identified in the BUGS.md study — any drift means a
   lookup or matching bug.
2. Spot-check a handful of `[NEW]` entries by hand against their source JSON file.
3. Run `--apply`.
4. Immediately re-run dry-run: expect zero `[NEW]` rows and zero files whose flag
   would still be corrected — proves the write was complete and the script is
   idempotent.
5. Confirm `tbl_cash_dividends` row count increased by exactly the reported new-row
   count, and every new row has `status='Estimate'`.

## Files touched

- `server/scripts/import_dividend_estimates.py` — new
- `dividends_analysis/json/*.json` — `already_in_tbl_cash_dividends` corrected in
  place, `--apply` only, only for files whose declaration is fully covered
- `server/instance/LTV Stocks.db` — new `Estimate` rows, `--apply` only

## Deployment

Local only. This script has no production equivalent — `dividends_analysis/` isn't
deployed to PythonAnywhere. If Estimate rows ever need to exist on production too,
that's a separate, explicit, later decision (e.g. re-running an equivalent process
there, or manual entry) — not part of this script's job.
