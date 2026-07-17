# ltv_app Maintenance Backlog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close five small, risk-ranked gaps found in a codebase analysis of `ltv_app`: a committed secret key, a LAN-exposed dev-server debugger, dead/unsafe request-logging code, an orphaned migrations tree, and a missing regression harness for the app's buggiest module.

**Architecture:** Five independent tasks, each touching a different file (or deleting a directory), executed and committed one at a time in risk-first order. No task depends on code introduced by an earlier task — they can be reviewed and landed independently, though the plan lists them in the agreed order.

**Tech Stack:** Python 3.13, Flask app factory (`ltv_app.create_app`), raw `sqlite3` (`get_db`), the `.venv` at `server/.venv`. No pytest suite exists in this copy — Task 5's "test" is a runnable harness script, same pattern as `scripts/verify_period_schedule.py`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-maintenance-backlog-design.md`.
- Run everything with `server/.venv/Scripts/python.exe`, cwd `server/`.
- The DB in use is `server/instance/LTV Stocks.db` (real client data). Tasks 1, 2, 3, 4 don't touch it at all. Task 5's harness only ever reads it (`SELECT`-only functions) — never mutate it.
- Never commit a real secret value. `server/config.py` is covered by the `/*` allowlist rule in `server/.gitignore` (no `!server/config.py` un-ignore exists) — confirmed not tracked. Any generated key goes only into that local, untracked file, never into a committed file or this plan.
- PA (PythonAnywhere) deployment is explicitly the user's own responsibility going forward ("I will handle PA deploy") — no task in this plan touches PA. Task 1 ends with a reminder for the user to set `SECRET_KEY` in PA's own `config.py` themselves.

---

## File Structure

- **Modify** `ltv_app/__init__.py` — replace the hardcoded `SECRET_KEY` default (Task 1).
- **Create** `config.py` (server root, untracked/gitignored) — local persisted secret key (Task 1).
- **Modify** `flask_app.py` — bind `127.0.0.1` instead of the LAN IP (Task 2).
- **Delete** `migrations/` — orphaned Alembic history for the abandoned `ltv2` rewrite (Task 3).
- **Modify** `ltv_app/blueprints/database/views.py` — remove dead/unsafe `log_request`/`save_log`/`_open_log_workbook` code (Task 4).
- **Create** `scripts/verify_positions_calc.py` — regression harness for `legacy_port/positions_calc.py` (Task 5).

---

### Task 1: Rotate the hardcoded secret key

**Files:**
- Modify: `ltv_app/__init__.py:1-4` (imports), `ltv_app/__init__.py:44-47` (`app.config.from_mapping(...)`)
- Create: `config.py` (server root — untracked)

**Interfaces:**
- Consumes: nothing new.
- Produces: `create_app()` still returns a working app; `SECRET_KEY` is no longer a fixed committed value.

- [ ] **Step 1: Generate a random key (do not paste the output into any committed file)**

Run:
```bash
.venv/Scripts/python.exe -c "import secrets; print(secrets.token_hex(32))"
```
Copy the printed 64-character hex string — you'll paste it into `config.py` in Step 2, and only there.

- [ ] **Step 2: Create the local `config.py`**

Create `server/config.py` (this file is NOT tracked by git — `server/.gitignore` starts with `/*` and has no `!config.py` rule):

```python
SECRET_KEY = "<paste the value generated in Step 1 here>"
```

- [ ] **Step 3: Replace the committed hardcoded default in `ltv_app/__init__.py`**

At the top of the file, change:
```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
```
to:
```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import secrets
```

In `create_app()`, change:
```python
    app.config.from_mapping(
        SECRET_KEY="acda5284c0cc9a93e828516b701ab77907cd9bfe5f4f00c5026059b2d7f58419",
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
    )
```
to:
```python
    app.config.from_mapping(
        # Random per-process fallback so a fresh clone still boots without a
        # committed secret. config.py (untracked) overrides this with a real,
        # persisted key for actual use — see Step 2 of this task.
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
    )
```

The existing `app.config.from_pyfile('config.py', silent=True)` a few lines below is unchanged — it already loads `config.py` when present and silently no-ops when it isn't, so it will pick up the file from Step 2 automatically.

- [ ] **Step 4: Verify the app boots and login still works**

Run:
```bash
.venv/Scripts/python.exe -c "
from ltv_app import create_app
app = create_app()
client = app.test_client()
r = client.get('/login')
print('status:', r.status_code)
print('secret key set:', bool(app.config['SECRET_KEY']))
"
```
Expected: `status: 200` and `secret key set: True`. (`/login` is the `auth` blueprint's route — `bp = Blueprint('auth', __name__, url_prefix='')` with `@bp.route('/login', ...)` in `ltv_app/blueprints/auth/views.py`.)

- [ ] **Step 5: Commit**

```bash
git add ltv_app/__init__.py
git commit -m "fix(security): stop hardcoding SECRET_KEY, generate a safe fallback

The committed default has been public in this repo since the ltv2 skeleton.
config.py (untracked, .gitignore's allowlist excludes it) now carries the
real persisted key for local use; a fresh clone with no config.py falls
back to a random per-process key instead of a fixed known value."
```

> **Reminder for the user (not a plan step — you do this on PA yourself):** confirm PA's own `config.py` at `/home/larrylilia/ltv_app/config.py` sets its own real `SECRET_KEY`, independent of this repo. If it doesn't, every session cookie on the live site is currently forgeable with the old public value until PA is updated with its own key.

---

### Task 2: Stop binding the dev server to the LAN IP

**Files:**
- Modify: `flask_app.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: local dev server reachable only at `127.0.0.1:5001`, not the LAN IP.

- [ ] **Step 1: Replace the LAN-IP bind**

Current `flask_app.py`:
```python
import socket

from ltv_app import create_app

app = create_app()

if __name__ == "__main__":
    host = socket.gethostbyname(socket.gethostname())
    port = 5001
    print(f"Starting host @ http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
```

Replace with:
```python
from ltv_app import create_app

app = create_app()

if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5001
    print(f"Starting host @ http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
```

(Drop the `import socket` line entirely — nothing else in this file uses it.)

- [ ] **Step 2: Verify the module still imports and the app factory still boots**

`flask_app.py` calls `create_app()` at import time (line 3, outside `if __name__ == "__main__":`), so importing it is enough to prove the change didn't break app creation — it does not start a listening server.

Run:
```bash
.venv/Scripts/python.exe -c "import flask_app; print('app created OK:', flask_app.app.name)"
grep -n "host = " flask_app.py
```
Expected: `app created OK: ltv_app`, and the grep line shows `host = "127.0.0.1"` (not the old `socket.gethostbyname(...)` call).

- [ ] **Step 3: Commit**

```bash
git add flask_app.py
git commit -m "fix(security): bind dev server to 127.0.0.1, not the LAN IP

Binding to socket.gethostbyname(socket.gethostname()) with debug=True exposed
Werkzeug's interactive debugger (arbitrary code execution) to anyone on the
same network segment. LAN access isn't needed for local dev."
```

---

### Task 3: Delete the orphaned `migrations/` directory

**Files:**
- Delete: `migrations/` (contains `alembic.ini`, `env.py`, `README`, `script.py.mako`, `versions/*.py` — 4 migration files)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing — this is a deletion with no code depending on it (`Migrate(app, db)` is never called anywhere in `create_app()`).

- [ ] **Step 1: Confirm nothing references `migrations/` before deleting**

Run:
```bash
grep -rn "Migrate\|migrations" ltv_app/ flask_app.py 2>/dev/null
```
Expected: no output (or only unrelated matches, e.g. a comment). If `Migrate(app, db)` or similar shows up wired into `create_app()`, STOP — that means migrations became live since the design was written; re-confirm with the user before deleting.

- [ ] **Step 2: Delete the directory**

```bash
git rm -r migrations/
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove orphaned migrations/ for the abandoned ltv2 rewrite

Migrate(app, db) is never called in create_app() — this Alembic history
belongs to ltv2, which has already been removed from this working copy.
Recoverable from git history or the original C:\\envs\\LTV\\server workspace
if ltv2 is ever revived."
```

---

### Task 4: Delete dead `log_request` code

**Files:**
- Modify: `ltv_app/blueprints/database/views.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `get_db()` and `base_variables()` behave identically (the removed code was already commented out / never called); no other file's behavior changes.

- [ ] **Step 1: Confirm nothing else references these names**

Run:
```bash
grep -rn "log_request\|save_log\|_open_log_workbook" ltv_app/ flask_app.py 2>/dev/null
```
Expected: matches only inside `ltv_app/blueprints/database/views.py` itself (the definitions and the commented-out call site). If anything outside that file shows up, STOP and re-check before deleting.

- [ ] **Step 2: Remove the dead code**

Current top of `ltv_app/blueprints/database/views.py`:
```python
import datetime
from flask import Blueprint, current_app, g, request
import sqlite3
import os
from openpyxl import Workbook, load_workbook

from .. auth import login_required
from ..bank import BankAccount
from ..currency import Currency
from ..stocks import Stocks

bp = Blueprint('database', __name__, url_prefix="/database")


@bp.route('/')
@login_required
def home():
    return "Database home"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row

    # log_request()

    return g.db


def log_request():
    request_url = str(request.url)
    request_data = ""
    if "user_url" not in g:
        if 'static' not in request_url:
            g.user_url = request_url
            save_log(request_url, request_data)
    else:
        if g.user_url != request_url:
            if 'static' not in request_url:
                g.user_url = request_url
                save_log(request_url, request_data)


def _open_log_workbook(filename):
    """data_logs.xlsx is gitignored, so a fresh clone does not have it."""
    if os.path.exists(filename):
        return load_workbook(filename)
    wb = Workbook()
    wb.active.title = "LOGS"
    return wb


def save_log(request_url, request_data):
    filename = os.path.join(current_app.instance_path, "data_logs.xlsx")
    wb = _open_log_workbook(filename)
    ws = wb["LOGS"]

    #  Go to next empty row
    row_num = 1
    date_time = ws[f"A{row_num}"].value
    while date_time:
        row_num += 1
        date_time = ws[f"A{row_num}"].value

    date_time = datetime.datetime.now()

    ws[f"A{row_num}"].value = date_time
    ws[f"B{row_num}"].value = request_url
    ws[f"C{row_num}"].value = request_data

    wb.save(filename)
    wb.close()
```

Replace that entire block (everything from the top of the file down through the end of `save_log`) with:
```python
from flask import Blueprint, current_app, g
import sqlite3

from .. auth import login_required
from ..bank import BankAccount
from ..currency import Currency
from ..stocks import Stocks

bp = Blueprint('database', __name__, url_prefix="/database")


@bp.route('/')
@login_required
def home():
    return "Database home"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row

    return g.db
```

(`request` is no longer used in this file once `log_request` is gone — dropped from the `flask` import. `datetime` and `os` were only used by the removed functions — dropped entirely. `openpyxl` import removed entirely. Everything from `@bp.before_app_request` / `base_variables()` onward in the file is unchanged — leave it exactly as-is.)

- [ ] **Step 3: Verify the app still boots and a page that hits `get_db()`/`base_variables()` still works**

Run:
```bash
.venv/Scripts/python.exe -c "
from ltv_app import create_app
app = create_app()
client = app.test_client()
r = client.get('/login')
print('status:', r.status_code)
"
```
Expected: `status: 200` (this route passes through `base_variables()`'s `before_app_request` hook, which calls `get_db()`).

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/database/views.py
git commit -m "chore: remove dead log_request/save_log request-logging code

The call site was already commented out and, as written, was unsafe to
re-enable: it sat outside get_db()'s 'if db not in g' guard (so it would
fire on every get_db() call in a request, not once per page view) and
save_log() rewrote the entire data_logs.xlsx workbook from scratch on every
call via a linear scan for the next empty row."
```

---

### Task 5: Regression harness for `legacy_port/positions_calc.py`

**Files:**
- Create: `scripts/verify_positions_calc.py`

**Interfaces:**
- Consumes: `ltv_app.create_app`, `ltv_app.blueprints.database.views.get_db`,
  `ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc._average`,
  `ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc._transactions_narrative`,
  `ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc.contract_records`,
  `ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc.position_records`,
  `ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer._inject_accu_only_positions`.
- Produces: a script that exits 0 (all match) or 1 (any mismatch), printing per-case PASS/FAIL.

Golden values below were captured directly from the real `instance/LTV Stocks.db` this session, from the exact bank/code/date combinations the three narrative/average bugs were reported and fixed against (bank `DBPe` = `bank_ref` 5 throughout):

| Case | Function | Inputs | Expected |
|---|---|---|---|
| A | `_transactions_narrative` | `bank_ref=5, code_ref=52 (9988 Alibaba), report_date=2026-07-10` | `'(7/6) Buy (Accu) 3,200 @ 133.8612 + (7/10) Buy (Accu) 5,400 @ 145.7204 = 108,150'` |
| B1 | `_transactions_narrative` | `bank_ref=5, code_ref=83 (2196), report_date=2026-07-10` | `'(7/6) Transfer-Out (to Sun Hung Kai Account No. 2) 35,000 @ 19.1237 = 0'` |
| B2 | `_average` | `bank_id='DBPe', code='2196', as_of_date=2026-07-10` | `'=669330.0/35000'` |
| C | `_average` (via `_inject_accu_only_positions`) | code `'3993'` (China Molybdenum) injected into `position_records(db, 5, 'DBPe', 'HKD', 2026-07-10)` | `average == '=602993.6/39000'`, `transactions == '(7/7) Buy (Accu) 39,000 @ 15.4454 = 39,000'` |

Case A pins the true-ending-balance fix (previously showed the stale beginning-of-week snapshot, `99,550`). Case B1/B2 pin the Transfer-Out destination label and the zero-balance last-average-on-record fallback (previously bare `0`) on the same transaction. Case C pins the ACCU-placeholder-vs-real-average fix (previously always showed the contract's strike price, `15.4454`, even though a real charge-inclusive average — `602993.6/39000` — was computable).

- [ ] **Step 1: Write the harness**

Create `scripts/verify_positions_calc.py`:

```python
"""Regression harness for ltv_stocks/legacy_port/positions_calc.py.

Pins known-good output (captured against the real instance/LTV Stocks.db) for
the four narrative/average bugs fixed in this codebase's 2026-07 session, so
a future change to _average, _transactions_narrative, or
_inject_accu_only_positions can't silently regress them. All functions here
are read-only (SELECT-only) — this script never mutates the database.

Run: server/.venv/Scripts/python.exe scripts/verify_positions_calc.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import (
    _average, _transactions_narrative, position_records,
)
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import _inject_accu_only_positions

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")
REPORT_DATE = date(2026, 7, 10)


def _open():
    app = create_app()
    app.config["DATABASE"] = DB_PATH
    ctx = app.app_context()
    ctx.push()
    return ctx, get_db()


def _case(label, actual, expected):
    if actual == expected:
        print(f"  {label}: PASS")
        return True
    print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")
    return False


def main():
    ctx, db = _open()
    try:
        ok = True

        # Case A: true ending balance in the narrative (was the stale
        # beginning-of-week snapshot, 99,550).
        ok &= _case(
            "A _transactions_narrative 9988@DBPe",
            _transactions_narrative(db, 5, 52, REPORT_DATE),
            "(7/6) Buy (Accu) 3,200 @ 133.8612 + (7/10) Buy (Accu) 5,400 @ 145.7204 = 108,150",
        )

        # Case B1: Transfer-Out destination label.
        ok &= _case(
            "B1 _transactions_narrative 2196@DBPe",
            _transactions_narrative(db, 5, 83, REPORT_DATE),
            "(7/6) Transfer-Out (to Sun Hung Kai Account No. 2) 35,000 @ 19.1237 = 0",
        )

        # Case B2: zero-balance -> last-average-on-record (was bare 0).
        ok &= _case(
            "B2 _average 2196@DBPe (zero balance)",
            _average(db, "DBPe", "2196", REPORT_DATE),
            "=669330.0/35000",
        )

        # Case C: ACCU-only placeholder uses the real charge-inclusive average
        # (was always the contract's strike price, 15.4454).
        accu = [r for r in contract_records(db, 5, "ACCU")
                if r["ccy_id"] == "HKD" and r["code"] == "3993"]
        positions = position_records(db, 5, "DBPe", "HKD", REPORT_DATE)
        injected = _inject_accu_only_positions(positions, accu, db, 5, "DBPe", REPORT_DATE)
        rec = injected.get("3993")
        ok &= _case("C average 3993@DBPe (ACCU-only)",
                    rec["average"] if rec else None, "=602993.6/39000")
        ok &= _case("C transactions 3993@DBPe (ACCU-only)",
                    rec["transactions"] if rec else None,
                    "(7/7) Buy (Accu) 39,000 @ 15.4454 = 39,000")
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the harness against the current (already-fixed) code**

Run: `.venv/Scripts/python.exe scripts/verify_positions_calc.py`
Expected: **all five cases PASS**, `RESULT: ALL PASS`, exit 0 — these bugs were already fixed earlier this session; this harness is locking in that fix, not reproducing the bug.

- [ ] **Step 3: Sanity-check the harness actually catches a regression**

Temporarily break one case to prove the harness isn't vacuously passing: in `ltv_app/blueprints/ltv_stocks/legacy_port/positions_calc.py`, in `_average`, comment out the `last_nz` fallback block (the `if last_nz:` branch added by the earlier fix) so a zero balance returns bare `0` again. Re-run:

Run: `.venv/Scripts/python.exe scripts/verify_positions_calc.py`
Expected: `B2 _average 2196@DBPe (zero balance): FAIL  expected '=669330.0/35000', got 0`, `RESULT: FAIL`, exit 1.

Then revert the temporary break (`git diff` should show no changes to `positions_calc.py` before continuing):
```bash
git diff ltv_app/blueprints/ltv_stocks/legacy_port/positions_calc.py
git checkout -- ltv_app/blueprints/ltv_stocks/legacy_port/positions_calc.py
```
Re-run once more to confirm it's back to `RESULT: ALL PASS`.

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_positions_calc.py
git commit -m "test(ltv_stocks): add regression harness for legacy_port narrative/average fixes

Pins the four bugs fixed this session (true ending balance, Transfer-Out
destination label, zero-balance last-average fallback, ACCU-placeholder
real-average) as goldens captured from the real instance DB, so future
changes to _average/_transactions_narrative/_inject_accu_only_positions
can't silently regress them."
```

---

## Self-Review

**Spec coverage:** Task 1 = spec's "Rotate the secret key" (1a-1c: safe default, verify boot, PA reminder documented as a post-commit note since PA is out of scope for this repo's tasks). Task 2 = spec's "dev-server bind" (2a-2b). Task 3 = spec's "delete migrations/" (3a, including the confirm-nothing-references-it guard). Task 4 = spec's "delete log_request" (4a-4b). Task 5 = spec's "legacy_port harness" (5a-5e: script created, three golden cases covering all three narrative/average code paths, wired into one runnable script with a documented table of expected values).

**Placeholder scan:** none — every step has runnable code, exact commands, and expected output. The one intentional placeholder-looking text (`<paste the value generated in Step 1 here>`) is a deliberate instruction to avoid ever committing a real secret, not an unresolved requirement.

**Type consistency:** `_transactions_narrative(db, bank_ref, code_ref, report_date)` and `_average(db, bank_id, code, as_of_date)` signatures in Task 5 match their definitions in `positions_calc.py` read this session (no `balance` parameter — already removed by the earlier fix). `_inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date)` matches its current 6-arg signature in `excel_writer.py`. `contract_records(db, bank_ref, product)` and `position_records(db, bank_ref, bank_id, ccy_id, report_date)` match their call sites in `excel_writer.py`'s `build_workbook`.

**Note on task independence:** all five tasks are independent of each other (different files, no shared new code) and can be landed in any order without breaking one another — the risk-first order here is a sequencing preference from the design, not a hard dependency.
