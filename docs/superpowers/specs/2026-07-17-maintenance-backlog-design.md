# ltv_app maintenance backlog — design

Date: 2026-07-17
Status: Approved

## Background

A codebase analysis of `ltv_app` (prompted by a pattern of subtle bugs found
this session in `legacy_port/positions_calc.py` and `excel_writer.py`)
surfaced five concrete issues, proportionate to this app's actual risk
profile: a small, single-developer, single-client internal admin/reporting
tool with real financial data, no test suite, and no CI. Explicitly out of
scope (considered and rejected as disproportionate): full ORM migration,
CI/CD pipeline, further service splitting, broad lint/format rollout.

## Execution model

Five steps, executed **one at a time**, risk-first. Each step lands as its
own reviewed, committed unit (same subagent-driven-development pattern used
for the period-schedule fix earlier this session: task brief → implement →
task-scoped review → commit) before starting the next step.

## Step 1 — Rotate the hardcoded secret key (small)

**Problem:** `ltv_app/__init__.py` hardcodes a `SECRET_KEY` default that has
been committed to the public repo since the `ltv2` skeleton. If PA's
gitignored `config.py` doesn't override it, every session cookie on the live
site is forgeable with a publicly known key.

**Steps:**
1a. Replace the hardcoded default with a safe non-production value — generated
    per-process (e.g. `secrets.token_hex(32)`) when no override is configured,
    so a fresh clone still boots, but no fixed value is ever committed again.
1b. Verify the local server still boots and login still works with the new
    default.
1c. Document (in this spec and, if warranted, a memory) that PA's own
    `config.py` must set its own real, persisted `SECRET_KEY` — this is a
    manual action item for the user on PA, not something this step touches,
    per the standing instruction that the user handles PA deployment.

## Step 2 — Stop binding the dev server to the LAN IP (small)

**Problem:** `flask_app.py` binds via
`socket.gethostbyname(socket.gethostname())` with `debug=True`, exposing
Werkzeug's interactive debugger (arbitrary code execution) to anyone on the
same network segment who triggers an unhandled exception. Confirmed with the
user: LAN access is not needed.

**Steps:**
2a. Change the bind host to `127.0.0.1`, dropping the LAN-IP auto-detect
    entirely.
2b. Verify the local server still starts and is reachable at
    `127.0.0.1:5001`.

## Step 3 — Delete the orphaned `migrations/` directory (small)

**Problem:** Real Alembic history for the abandoned `ltv2` SQLAlchemy
rewrite. `Migrate(app, db)` is never called in `create_app()`; nothing
references it. Confirmed with the user: delete rather than leave a note —
fully recoverable from git history / the original `C:\envs\LTV\server`
workspace if `ltv2` is ever revived.

**Steps:**
3a. Delete `migrations/`, commit with a note explaining recoverability.

## Step 4 — Delete dead `log_request` code (small)

**Problem:** `blueprints/database/views.py` has a commented-out
`log_request()` call inside `get_db()`, plus `log_request()`, `save_log()`,
and `_open_log_workbook()` themselves. Investigation this session found the
call site sits *outside* the `if 'db' not in g:` guard, so if re-enabled as-is
it would fire on every `get_db()` call in a request (there are several per
request), not once per page view — and `save_log()` does a full linear scan
from row 1 plus a full workbook rewrite via openpyxl on every call, an
O(n²)-ish cost that would visibly slow the app as the log grows. Confirmed
with the user: delete rather than fix-and-re-enable.

**Steps:**
4a. Remove `log_request()`, `save_log()`, `_open_log_workbook()`, the
    openpyxl import, and the commented call-site from
    `blueprints/database/views.py`.
4b. Grep-confirm no other code references these names before removing.

## Step 5 — Regression harness for `legacy_port` (medium)

**Problem:** `positions_calc.py` and `excel_writer.py` were the source of
four distinct correctness bugs fixed this session (Transfer-Out destination
label, stale running balance in the narrative, ACCU-placeholder average vs.
strike price, zero-balance → last-average-on-record fallback), all found by
hand-comparing generated Excel output against a live DB — none caught
automatically. Confirmed with the user: goldens should be pinned against the
real local DB (same pattern as `scripts/verify_period_schedule.py`), not a
synthetic fixture DB.

**Steps:**
5a. Create `scripts/verify_positions_calc.py`, following the structure of
    `verify_period_schedule.py`.
5b. Pin golden values for `_transactions_narrative` (Transfer-Out destination
    label + correct ending balance) against real bank/code/date combos drawn
    from the bugs fixed this session.
5c. Pin golden values for `_average()`'s zero-balance → last-average-on-record
    fallback.
5d. Pin golden values for `_inject_accu_only_positions`'s real-average-vs-
    strike-placeholder logic.
5e. Wire all cases into one runnable script; document how to run it and what
    it checks (comment header, same style as `verify_period_schedule.py`'s
    `GOLDEN` dict rationale).

## Out of scope

- Full ORM migration — raw `sqlite3`/`get_db()` pattern is consistent across
  ~30 blueprints; bad churn-to-value ratio for a solo, no-test codebase.
- CI/CD pipeline — no team, no PR flow to gate.
- Further splitting of `localhost` / `ltv_app` — adds deployment surface for
  no correctness benefit.
- Broad lint/format tooling rollout — bug history here is logic errors, not
  style.
