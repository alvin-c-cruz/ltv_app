# Dividend Estimates Production Entry (browser-driven) — design

Date: 2026-07-23
Status: Approved, pending execution

## Context

`server/scripts/import_dividend_estimates.py` (built, reviewed, merged to `main`
earlier today) computes and can write `status='Estimate'` rows into
`tbl_cash_dividends` from `dividends_analysis/json/`. Its `--apply` mode writes
directly to whichever SQLite file it's pointed at.

The user wants the actual data entry to happen through the live production webapp's
own `/dividends/add` form instead — going through the app's real save path on the
system Larry/staff actually use daily ("webapp" = `larrylilia.pythonanywhere.com`
in this user's established vocabulary, distinct from "ltv_app" = the local copy),
rather than a direct-to-SQLite batch write. This is a deliberate substitute for
running `--apply` locally, not an addition to it — local stays as-is until the
user's next routine PA resync.

## Scope

No new code. This is an operational task:

1. Deploy the already-merged importer script to production (`git pull` — code-only,
   doesn't touch the running app).
2. Run it in **dry-run mode on production** to get production's own accurate
   "what's actually missing" list (not assumed to be the same 264 rows the local
   dry-run showed — production is the live system of record; local may be behind
   or diverged on what's actually been entered).
3. Drive the real `/dividends/add` form, once per missing declaration/bank pair,
   via browser automation, after the user logs in themselves.

Out of scope: any code changes, running `--apply` against local, building a new
MCP server, batch/bulk submission (the app has no such endpoint — this goes through
the same single-row Add form a human would use).

## 1. Getting production's accurate list

`git pull origin main` on `/home/larrylilia/ltv_app` (adds the script file only —
already-reviewed code, no schema/behavior change to the running app). Run
`python scripts/import_dividend_estimates.py` (no `--apply`) via the PA console —
read-only, safe, matches how every other production check this session was done.
Its dry-run report is the authoritative "what to submit" list for this task,
computed against production's real `tbl_cash_dividends`/`tbl_bank_account`/
`tbl_code`/`tbl_currency` data.

## 2. Authentication handoff

Claude opens `larrylilia.pythonanywhere.com`'s login page in a browser tab. The
user enters their own credentials in that tab — Claude never sees or handles them,
per the standing rule against entering passwords into any field. Once the user
confirms they're logged in, Claude proceeds using that authenticated session for
every subsequent form submission.

## 3. Form-filling mechanics

For each row from the production dry-run's `[NEW]` list, on `/dividends/add`:

- **Bank / Stock / Currency dropdowns**: matched by visible label (bank's short
  code + name, stock code, currency code), never by the underlying `ref_num`
  value — production's and local's reference-table IDs aren't guaranteed to
  match even though the business codes (`bank_id`, `code`, `ccy_id`) are stable.
- **Declaration/Ex/Record/Pay-Out dates, Dividends per share, Nominal (quantity)**:
  filled from the production dry-run's resolved values directly.
- **Status**: `Estimate`.
- **Tax / Charges**: `0` (no WHT source in the source JSON, matching the
  importer's own convention).

After each submission, verify it actually landed (the "Dividend saved" flash
message, and the row appearing) before moving to the next. A submission that
doesn't verify cleanly stops the run — report it rather than continuing blind.

## 4. Rollout: test batch, then the rest

1. Submit the first 3-5 rows from production's list only.
2. Stop, report results, let the user confirm they look correct on the live site.
3. Continue through the remaining rows, verifying each, reporting progress
   periodically (this is sequential browser automation against a live site, not a
   batch operation — expect it to take a while).

**Resumability is free**: since dedup is a live DB check inside the reused script
(not a separate progress log), an interrupted run can simply be resumed by
re-running the production dry-run — already-submitted rows show as
`[ALREADY IN DB]` and are skipped automatically, with no separate tracking needed.

## Error handling

- A submission that fails to verify (no flash message, row doesn't appear, an
  unexpected form validation error) stops the run immediately — report the
  specific row and what happened, don't skip past it and keep going.
- If the browser session appears to have lost authentication partway through
  (e.g. redirected to login), stop and ask the user to re-authenticate rather
  than attempting to proceed or guess.

## Verification

No test suite applies here — this is a live operational task against production.
"Verification" is the per-row check described in section 3, plus the test-batch
gate in section 4 before committing to the full run.
