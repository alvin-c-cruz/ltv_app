# Dividends bug fixes — design

Date: 2026-07-23
Status: Approved, pending implementation

## Context

`BUGS.md` tracks four open issues in the `dividends` blueprint, all found in the
same 2026-07-15 session while scoping the `dividends-analysis` skill:

1. Home page hardcodes `year = "2022"`, so no dividend recorded since then is
   ever visible without editing source code.
2. `tbl_cash_dividends` has no Record Date (or Declaration Date) column, so
   entitlement details fetched externally can't be stored in the DB.
3. No Excel/PDF export exists for dividends, unlike `portfolio`.
4. Estimate → Actual status promotion is fully manual, with no visual cue that
   a row is overdue.

All four are small and live in the same blueprint, and #1/#3 share the same
date-range plumbing, so they're handled as one spec rather than split up.
Bug #4's recommendation has two parts — (a) auto-create Estimate rows from
fetched dividend declarations, and (b) a visible "pending Actual" indicator.
Part (a) depends on wiring in the separate `dividends-analysis` skill's fetch
pipeline (a real integration project, not a bug fix) and is explicitly
**out of scope** here; only part (b) is built.

## Scope

Fix, in the `dividends` blueprint:

1. Year hardcoded to 2022 → real GET-based date-range filter, matching the
   `workflow` blueprint's `?date_from=...&date_to=...` pattern. The filter
   form on `home.html` already exists and is already wired to POST to
   `dividends.home` — the route just never reads it.
2. Add `record_date` and `declaration_date` columns to `tbl_cash_dividends`,
   wired into the model, form, list, and Excel export.
3. Add an Excel export (`dividends.export`), structured like
   `portfolio/extensions/create_excel.py` — one sheet per bank account.
4. Add a visible "Estimate (overdue)" indicator on the Status cell when
   `status == 'Estimate'` and `pay_out` is in the past.

Out of scope: auto-creating Estimate rows from `dividends-analysis` fetch
data (bug #4 part (a) — separate integration project), PDF export (Excel
only, matching `portfolio`'s existing pattern), and PythonAnywhere deployment
of this change (a separate, explicit step — see Deployment below for the
sequencing that step must follow).

## 1. Date-range filter

**Root cause:** `dividends.home()` (`ltv_app/blueprints/dividends/views.py:21`)
unconditionally sets `year = "2022"` and never reads `request.form` or
`request.args`, even though `home.html`'s filter form (`start_date`/`end_date`
inputs, POSTing to `dividends.home`) already exists in the template.

**Fix:**
- `home.html`: change the filter `<form>` from `method="post"` to
  `method="get"` (field names unchanged) — makes the filtered view a real,
  bookmarkable URL instead of a POST with no persisted state.
- `views.py`'s `home()`: route drops `POST` (GET-only, matching `workflow`).
  Reads `start_date`/`end_date` from `request.args`; if either is missing,
  defaults to the current year (`ph_today()` from `ltv_app/tz.py`, Jan 1 to
  Dec 31) instead of the literal `"2022"`. The existing SQL is already
  parameterized on these two values — only their source changes.

Note: since nearly all existing dividend data predates 2026 (that's the whole
reason this bug went unnoticed), defaulting to "current year" will likely
show zero rows on first load until the range is adjusted — expected, not a
regression.

## 2. Schema: Record Date / Declaration Date

**Root cause:** `tbl_cash_dividends` only has `ex_date`/`pay_out`. Record Date
(which determines entitlement, and is often distinct from Ex-Date) and
Declaration Date aren't stored anywhere; a commented-out unused
`DividendsDeclaration` stub in `models.py` already anticipated this gap.

**Fix:**
- Schema: one-time manual `ALTER TABLE tbl_cash_dividends ADD COLUMN
  declaration_date TIMESTAMP;` and `... ADD COLUMN record_date TIMESTAMP;`
  against both the local and production DBs (no migration tooling is wired
  into this app — see Deployment for sequencing). Nullable; existing rows get
  `NULL` in both — no backfill attempted, since nothing stored today reliably
  implies either date.
- `views.py`'s `create_table()`: add both columns so a from-scratch table
  matches.
- `models.py`'s `CashDividends`: add `declaration_date: str = None` and
  `record_date: str = None`.
- `forms.py`: add both as `DateField`s **without** `DataRequired` — optional,
  since older/estimate rows won't always have them. `views.py`'s `add()`/
  `edit()` convert blank form input to `None` on save; when populated, same
  `str(...)[:10]` truncation as `ex_date`/`pay_out`.
- Column order — real-world chronological order, not appended at the end:
  **Declaration Date → Ex Date → Record Date → Pay-Out Date**, on the Add/Edit
  forms, the list table, and the Excel export.

## 3. Excel export

**Root cause:** `portfolio/extensions/create_excel.py` generates a
downloadable Excel report of positions; `dividends` has no equivalent.

**Fix:**
- New `dividends/extensions/create_excel.py` (+ `extensions/__init__.py`
  re-exporting `CreateExcel`), structured like `portfolio`'s: `CreateExcel(path,
  start_date, end_date, db)` builds `f"{start_date}_to_{end_date}
  dividends.xlsx"`.
- Iterates all bank accounts (ordered by `priority`, same as `portfolio`) and
  creates one sheet per account keyed by `bank_id` (short account code —
  matches `portfolio`'s convention, avoids Excel's 31-char/invalid-character
  sheet-name limits). Accounts with no dividends in range still get a
  header-only sheet, for consistent structure across exports.
- Columns per sheet, same order as the list table: Stock Name, Code,
  Quantity, Declaration Date, Ex Date, Record Date, Pay-Out Date, Ccy,
  Div/Share, Gross Amount, Tax/Charges, Net Amount, Status.
- New route `dividends.export` (GET): same `start_date`/`end_date` args and
  defaulting as `home()`; saves into `instance/temp/`; serves via
  `send_file(..., as_attachment=True)` (same pattern as
  `portfolio.home()`).
- `home.html`: "Download Excel" button next to "Add dividend", linking to
  `dividends.export` with the currently-active date range passed through, so
  the download always matches what's on screen.

## 4. Pending-Actual indicator

**Root cause:** `tbl_cash_dividends.status` supports `"Actual"`/`"Estimate"`,
but nothing flags a row still marked `Estimate` after its Pay Out date has
passed — promoting it is a fully manual, easy-to-forget step.

**Fix:**
- `home()` passes `today = str(ph_today())` into the template context (no
  per-row mutation — `sqlite3.Row` is read-only, and ISO `YYYY-MM-DD` strings
  compare correctly as plain strings).
- `home.html`'s Status cell: when `dividend.status == 'Estimate'` and
  `dividend.pay_out < today`, render `"Estimate (overdue)"` styled with the
  app's existing amber warning treatment (`rgba(217,119,6,...)` — same as the
  missing Bank Reference No. flag in `term_sheet` and the period-schedule
  warning banner), for visual consistency. Otherwise render the status
  normally.

## Verification

No test suite exists in this copy. Verification, matching how earlier fixes
this session were verified:

1. Python syntax checks (`ast.parse`) and Jinja template parse checks on all
   touched files.
2. A scripted check (direct sqlite3, then via `CashDividends`) that the new
   columns exist and round-trip correctly through the model/form.
3. End-to-end render checks via Flask's test client (simulated superuser
   session, same technique used for the `term_sheet` work this session)
   against the **local** DB: `GET /dividends/` (default range, explicit
   range), `GET /dividends/add`, `GET /dividends/edit/<ref>`,
   `GET /dividends/export` (confirm it returns a valid `.xlsx` with the
   expected sheets/columns).
4. The pending-Actual indicator's Jinja conditional is verified against a
   fabricated row rendered in isolation, rather than inserting throwaway rows
   into real dividend data.

## Files touched

- `ltv_app/blueprints/dividends/views.py` — date-range filter, `create_table()`
  columns, `add()`/`edit()` optional-field handling, new `export` route
- `ltv_app/blueprints/dividends/models.py` — `CashDividends` new fields
- `ltv_app/blueprints/dividends/forms.py` — new optional `DateField`s
- `ltv_app/blueprints/dividends/pages/dividends/home.html` — GET filter form,
  new columns, Download Excel button, pending-Actual indicator
- `ltv_app/blueprints/dividends/pages/dividends/add.html`,
  `edit.html` — new form fields
- `ltv_app/blueprints/dividends/extensions/__init__.py`,
  `create_excel.py` — new export module

## Deployment

Schema change must land before code that depends on it, on **each**
environment independently (unlike a data-value correction, this is a
code+schema change, so — unlike the earlier #1319 fix — it applies to local
*and* production, not production-only):

1. Implement all code changes locally.
2. Run both `ALTER TABLE` statements against the local `instance/LTV
   Stocks.db` first, so local testing has the columns.
3. Test locally (see Verification).
4. Commit to `server`'s git repo, push to `main`.
5. Run the same two `ALTER TABLE` statements against **production**'s DB via
   the PythonAnywhere console — before deploying new code, so it's a safe
   no-op for the currently-running old code.
6. `git pull origin main` on PythonAnywhere + reload the web app (existing
   deploy procedure).
7. Verify live: load `/dividends/` on production, confirm no errors,
   spot-check filter/export/indicator.
