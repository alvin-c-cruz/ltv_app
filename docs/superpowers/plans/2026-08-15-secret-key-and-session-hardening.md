# Secret Key and Session Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist `ltv_app`'s `SECRET_KEY` so restarts stop logging everyone out, and close three adjacent hardening gaps — an interpolated `ref_num` in `Model.save()`, 24 untyped route converters, and an unset `SameSite` cookie attribute.

**Architecture:** Four independent single-file changes, each with its own verification script under `scripts/`, committed one at a time. No task depends on code introduced by an earlier task; they are ordered by user-visible value. Items 1 and 4 also require a manual edit to `instance/config.py` on PythonAnywhere, which is deployment state and cannot ride along in a git pull.

**Tech Stack:** Python 3.13, Flask app factory (`ltv_app.create_app`), raw `sqlite3`, the venv at `server/.venv`. No pytest suite exists in this copy — each task's "test" is a runnable `scripts/verify_*.py` script, matching `verify_status_grid.py` / `verify_positions_calc.py`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-15-secret-key-and-session-hardening-design.md`.
- Run everything with `server/.venv/Scripts/python.exe`, cwd `server/`.
- `server/instance/LTV Stocks.db` is real client data. **No task in this plan reads or writes it.** Task 2's verification uses `sqlite3.connect(":memory:")` exclusively.
- **Never commit a real secret.** The generated `SECRET_KEY` goes only into `server/instance/config.py`, which is untracked. Never paste the key into a commit message, a plan, a spec, or terminal output that gets quoted back.
- `server/.gitignore` is an allowlist (`/*` then `!path` rules). `/instance/` is re-included but `/instance/*` excludes its contents, so `instance/config.py` is already ignored — confirm with `git check-ignore` rather than assuming.
- Do **not** set `SESSION_COOKIE_SECURE=True` in code. It would stop the session cookie being sent over `http://127.0.0.1:5001` and break local development login.
- Do **not** add `CSRFProtect` — explicitly out of scope per the spec's Non-goals.
- Do **not** change `PERMANENT_SESSION_LIFETIME`. `auth/views.py:35` calls `login_user(user)` without `remember=True` and nothing sets `session.permanent`, so the lifetime is inert and changing it would be a no-op.

---

## File Structure

- **Modify** `ltv_app/__init__.py:45-51` — correct the misleading `config.py` path comment (Task 1); add `SESSION_COOKIE_SAMESITE` (Task 4).
- **Create** `instance/config.py` (untracked) — the persisted `SECRET_KEY` (Task 1).
- **Create** `scripts/verify_secret_key.py` — Task 1's test.
- **Modify** `ltv_app/blueprints/data_model/__init__.py:47` — parameterise `ref_num` (Task 2).
- **Create** `scripts/verify_model_save_sql.py` — Task 2's test.
- **Modify** 23 route decorators across `dividends/views.py`, `fixings/views.py`, `term_sheet/views.py`, `transactions/views.py` (Task 3).
- **Create** `scripts/verify_route_converters.py` — Task 3's test.
- **Create** `scripts/verify_session_cookie.py` — Task 4's test.

---

## Task 1: Persist `SECRET_KEY`

**Files:**
- Create: `server/instance/config.py` (untracked — never committed)
- Modify: `server/ltv_app/__init__.py:45-51`
- Test: `server/scripts/verify_secret_key.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `instance/config.py` as the established home for deployment-specific config. Task 4 adds `SESSION_COOKIE_SECURE = True` to the PythonAnywhere copy of this same file.

- [ ] **Step 1: Confirm `instance/config.py` is gitignored before creating it**

Run:
```bash
git check-ignore -v instance/config.py
```
Expected: a line naming `.gitignore` and the `/instance/*` rule. If this prints nothing, **stop** — the file would be committable and the `.gitignore` needs fixing first.

- [ ] **Step 2: Write the failing test**

Create `server/scripts/verify_secret_key.py`:

```python
"""Verification that SECRET_KEY is persisted rather than regenerated per process.

create_app() falls back to secrets.token_hex(32) when no config file supplies a
key. That fallback runs on every call, so two create_app() calls return
different keys -- which is exactly why every app restart and PythonAnywhere
reload invalidates all sessions. Once instance/config.py supplies a real key,
both calls must return the same one.

Never prints the key itself.

Run: server/.venv/Scripts/python.exe scripts/verify_secret_key.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

CONFIG = os.path.join(SERVER, "instance", "config.py")

failures = []

present = os.path.exists(CONFIG)
if not present:
    failures.append(f"missing {CONFIG} -- the persisted key lives there")

first = create_app().config["SECRET_KEY"]
second = create_app().config["SECRET_KEY"]

if not first:
    failures.append("SECRET_KEY is empty")
if first != second:
    failures.append("SECRET_KEY differs between two create_app() calls -- "
                    "still using the per-process fallback")

print(f"instance/config.py present : {present}")
print(f"key stable across boots    : {first == second}")
print(f"key length                 : {len(first)}")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe scripts/verify_secret_key.py`

Expected: exit code 1, with output including
```
instance/config.py present : False
key stable across boots    : False
FAIL: missing ...\instance\config.py -- the persisted key lives there
FAIL: SECRET_KEY differs between two create_app() calls -- still using the per-process fallback
```

- [ ] **Step 4: Generate a key and write `instance/config.py`**

Run:
```bash
./.venv/Scripts/python.exe -c "import secrets; print('SECRET_KEY = \"%s\"' % secrets.token_hex(32))" > instance/config.py
```

This writes the file without the key ever appearing in terminal output. Confirm the shape without revealing the value:
```bash
./.venv/Scripts/python.exe -c "print(open('instance/config.py').read()[:14] + '...')"
```
Expected: `SECRET_KEY = "...`

- [ ] **Step 5: Fix the misleading comment in the app factory**

In `server/ltv_app/__init__.py`, replace lines 45-51:

```python
    app.config.from_mapping(
        # Random per-process fallback so a fresh clone still boots without a
        # committed secret. config.py (untracked) overrides this with a real,
        # persisted key for actual use — see Step 2 of this task.
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
    )
```

with:

```python
    app.config.from_mapping(
        # Random per-process fallback so a fresh clone still boots without a
        # committed secret. Overridden below by instance/config.py (untracked).
        # NOTE: the app is built with instance_relative_config=True, so
        # from_pyfile('config.py') resolves against instance_path -- the file
        # must be at instance/config.py, NOT the server/ root.
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
    )
```

Leave `app.config.from_pyfile('config.py', silent=True)` on line 54 unchanged — it is already correct.

- [ ] **Step 6: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe scripts/verify_secret_key.py`

Expected: exit code 0, ending in
```
instance/config.py present : True
key stable across boots    : True
key length                 : 64
PASS
```

- [ ] **Step 7: Confirm the secret did not become committable**

Run:
```bash
git status --short
```
Expected: `instance/config.py` does **not** appear. Only `ltv_app/__init__.py` and `scripts/verify_secret_key.py` should be listed.

- [ ] **Step 8: Commit**

```bash
git add ltv_app/__init__.py scripts/verify_secret_key.py
git commit -m "fix: persist SECRET_KEY via instance/config.py so restarts stop invalidating sessions"
```

- [ ] **Step 9: Apply the same file on PythonAnywhere**

The code change alone does nothing on the server — without `instance/config.py` there, the fallback still runs and the logouts continue. On PythonAnywhere (account `larrylilia`, via `alvinccruz`'s teacher access), in a Bash console:

```bash
cd /home/larrylilia/ltv_app
git pull
python3 -c "import secrets; print('SECRET_KEY = \"%s\"' % secrets.token_hex(32))" > instance/config.py
```

Then reload the web app from the Web tab. Use a **different** key than the local one — they are independent deployments. Verify by logging in, reloading the web app, and confirming the session survives.

---

## Task 2: Parameterise `ref_num` in `Model.save()`

**Files:**
- Modify: `server/ltv_app/blueprints/data_model/__init__.py:47`
- Test: `server/scripts/verify_model_save_sql.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: no signature change. `Model.save()` keeps its `save(self) -> None` shape; only the SQL it emits changes.

- [ ] **Step 1: Write the failing test**

Create `server/scripts/verify_model_save_sql.py`:

```python
"""Verification that Model.save() parameterises ref_num instead of interpolating it.

save() puts ref_num in BOTH the parameterised SET clause and (before this fix)
an interpolated WHERE clause. The deployed schema masks the bug:
tbl_stock_contract.ref_num is INTEGER PRIMARY KEY, which rejects a non-integer
payload when it is bound to SET, so the injection dies before WHERE matters.

That protection is incidental to the column type, not intended by the code.
So this test MUST exercise a plain INTEGER column, where the bug is actually
reachable, as well as the deployed INTEGER PRIMARY KEY shape.

Never touches instance/LTV Stocks.db -- in-memory databases only.

Run: server/.venv/Scripts/python.exe scripts/verify_model_save_sql.py
"""
import os
import sqlite3
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app.blueprints.data_model import Model

PAYLOAD = "1 OR 1=1"


@dataclass
class Toy(Model):
    ref_num: int = None
    reference: str = None

    def __post_init__(self):
        self.table_name = "toy"


def fresh(coldef):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(f"CREATE TABLE toy (ref_num {coldef}, reference TEXT)")
    db.executemany("INSERT INTO toy (ref_num, reference) VALUES (?,?)",
                   [(1, "one"), (2, "two"), (3, "three")])
    db.commit()
    return db


def attack(coldef):
    """Return (outcome, rows_overwritten) for the injection payload."""
    db = fresh(coldef)
    toy = Toy(db=db)
    toy.ref_num = PAYLOAD          # what term_sheet.edit assigns from the URL
    toy.reference = "PWNED"
    try:
        toy.save()
    except Exception as exc:
        return f"raised {type(exc).__name__}", 0
    hit = db.execute("SELECT COUNT(*) c FROM toy WHERE reference='PWNED'").fetchone()["c"]
    return "completed", hit


def legitimate():
    """A normal integer update must still work and touch exactly one row."""
    db = fresh("INTEGER")
    toy = Toy(db=db)
    toy.ref_num = 2
    toy.reference = "updated"
    toy.save()
    value = db.execute("SELECT reference FROM toy WHERE ref_num=2").fetchone()["reference"]
    touched = db.execute("SELECT COUNT(*) c FROM toy WHERE reference='updated'").fetchone()["c"]
    return value, touched


failures = []

outcome, hit = attack("INTEGER")
print(f"attack / plain INTEGER       : save() {outcome}, {hit} of 3 rows overwritten")
if hit > 1:
    failures.append("injection succeeded on a plain INTEGER column -- "
                    "ref_num is still interpolated into the WHERE clause")

outcome, hit = attack("INTEGER PRIMARY KEY")
print(f"attack / INTEGER PRIMARY KEY : save() {outcome}, {hit} of 3 rows overwritten")
if hit > 1:
    failures.append("injection succeeded on an INTEGER PRIMARY KEY column")

value, touched = legitimate()
print(f"legitimate update            : ref_num=2 -> {value!r}, {touched} row(s) touched")
if value != "updated" or touched != 1:
    failures.append(f"a normal update broke: got {value!r} on {touched} row(s), "
                    "expected 'updated' on exactly 1")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe scripts/verify_model_save_sql.py`

Expected: exit code 1, with
```
attack / plain INTEGER       : save() completed, 3 of 3 rows overwritten
attack / INTEGER PRIMARY KEY : save() raised IntegrityError, 0 of 3 rows overwritten
legitimate update            : ref_num=2 -> 'updated', 1 row(s) touched
FAIL: injection succeeded on a plain INTEGER column -- ref_num is still interpolated into the WHERE clause
```

This is the important line: the deployed shape already passes, the plain column does not. Do not "fix" the test to only check the deployed shape.

- [ ] **Step 3: Parameterise the WHERE clause**

In `server/ltv_app/blueprints/data_model/__init__.py`, replace line 47:

```python
            self.db.execute(f"UPDATE {self.table_name} set {', '.join(fields)} WHERE ref_num={self.ref_num};", values)
```

with:

```python
            self.db.execute(
                f"UPDATE {self.table_name} set {', '.join(fields)} WHERE ref_num=?;",
                values + [self.ref_num],
            )
```

`values` is built as a list comprehension on the line above, so `+ [...]` is safe. `{self.table_name}` stays interpolated — it is always a class constant set in `__post_init__`, never request data.

Leave `get()` on line 65 unchanged. Its `{", ".join(clause)}` interpolates filter *keys*, which are always code-supplied keyword names, and its values are already bound.

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe scripts/verify_model_save_sql.py`

Expected: exit code 0, with
```
attack / plain INTEGER       : save() completed, 0 of 3 rows overwritten
attack / INTEGER PRIMARY KEY : save() completed, 0 of 3 rows overwritten
legitimate update            : ref_num=2 -> 'updated', 1 row(s) touched
PASS
```

- [ ] **Step 5: Confirm no regression in the modules that call `save()`**

Run: `./.venv/Scripts/python.exe scripts/verify_period_schedule.py`

Expected: the same PASS output it gave before this change. This exercises `term_sheet`, the heaviest `Model.save()` consumer.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/data_model/__init__.py scripts/verify_model_save_sql.py
git commit -m "fix: parameterise ref_num in Model.save() instead of interpolating it into SQL"
```

---

## Task 3: Type the route converters

**Files:**
- Modify: `server/ltv_app/blueprints/dividends/views.py:111,158`
- Modify: `server/ltv_app/blueprints/fixings/views.py:95,146,158`
- Modify: `server/ltv_app/blueprints/term_sheet/views.py:185,310,338,346,360,374,388,397,437,543`
- Modify: `server/ltv_app/blueprints/transactions/views.py:260,370,406,425,442,534,571,590`
- Test: `server/scripts/verify_route_converters.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: view functions in these four blueprints now receive `int` for `ref_num`/`contract_ref`/`period_ref` rather than `str`. No `url_for` call needs changing — every caller already passes a database integer (`row.ref_num`, `accu.ref_num`, `decu.ref_num`, `ts.id`), verified across templates and views.

- [ ] **Step 1: Write the failing test**

Create `server/scripts/verify_route_converters.py`:

```python
"""Verification that every ref-style route param is typed <int:...>.

An untyped <ref_num>/<contract_ref>/<period_ref> lets a non-integer reach the
view, turning a malformed URL into an HTTP 500 instead of a clean 404, and
feeding an unvalidated string into model code.

<source> is deliberately NOT included -- it is an enum-like segment resolved
through a hardcoded dict in lock/charges/workflow and must stay a string.

Routing happens before login_required, so the 404 probes need no auth.

Run: server/.venv/Scripts/python.exe scripts/verify_route_converters.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

UNTYPED = ("<ref_num>", "<contract_ref>", "<period_ref>")
PROBES = [
    "/term-sheet/abc/view",
    "/term-sheet/edit/abc",
    "/term-sheet/abc/xyz/delete",
    "/trades/abc/edit",
    "/trades/short/abc/edit",
    "/dividends/edit/abc",
    "/fixings/abc/edit",
]

app = create_app()
failures = []

offenders = sorted(rule.rule for rule in app.url_map.iter_rules()
                   if any(token in rule.rule for token in UNTYPED))
print(f"untyped ref rules remaining: {len(offenders)}")
for rule in offenders:
    print("  ", rule)
    failures.append(f"untyped rule: {rule}")

client = app.test_client()
for path in PROBES:
    status = client.get(path).status_code
    print(f"GET {path:28} -> {status}")
    if status != 404:
        failures.append(f"{path} returned {status}, expected 404")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe scripts/verify_route_converters.py`

Expected: exit code 1, listing 23 untyped rules and showing probes returning `302` (redirect to login) or `500` rather than `404`.

- [ ] **Step 3: Convert `dividends/views.py`**

Line 111: `@bp.route("/edit/<ref_num>", methods=["GET", "POST"])`
→ `@bp.route("/edit/<int:ref_num>", methods=["GET", "POST"])`

Line 158: `@bp.route("/delete/<ref_num>")`
→ `@bp.route("/delete/<int:ref_num>")`

- [ ] **Step 4: Convert `fixings/views.py`**

Line 95: `@bp.route('/<ref_num>/edit', methods=['GET', 'POST'])`
→ `@bp.route('/<int:ref_num>/edit', methods=['GET', 'POST'])`

Line 146: `@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])`
→ `@bp.route('/<int:ref_num>/delete', methods=['GET', 'POST'])`

Line 158: `@bp.route('/<ref_num>/unlock', methods=['GET'])`
→ `@bp.route('/<int:ref_num>/unlock', methods=['GET'])`

- [ ] **Step 5: Convert `term_sheet/views.py`**

| Line | From | To |
|---|---|---|
| 185 | `"/edit/<contract_ref>"` | `"/edit/<int:contract_ref>"` |
| 310 | `"/<contract_ref>/data"` | `"/<int:contract_ref>/data"` |
| 338 | `"/<contract_ref>/view"` | `"/<int:contract_ref>/view"` |
| 346 | `"/<contract_ref>/lock"` | `"/<int:contract_ref>/lock"` |
| 360 | `"/<contract_ref>/unlock"` | `"/<int:contract_ref>/unlock"` |
| 374 | `"/<contract_ref>/delete"` | `"/<int:contract_ref>/delete"` |
| 388 | `"/<contract_ref>/<period_ref>/delete"` | `"/<int:contract_ref>/<int:period_ref>/delete"` |
| 397 | `"/<contract_ref>/set-inactive"` | `"/<int:contract_ref>/set-inactive"` |
| 437 | `"/<contract_ref>/set-active"` | `"/<int:contract_ref>/set-active"` |
| 543 | `"/<contract_ref>/add-line"` | `"/<int:contract_ref>/add-line"` |

Leave the `methods=[...]` argument of each decorator exactly as it is. Note line 388 has **two** params to convert.

- [ ] **Step 6: Convert `transactions/views.py`**

| Line | From | To |
|---|---|---|
| 260 | `'/<ref_num>/edit'` | `'/<int:ref_num>/edit'` |
| 370 | `'/<ref_num>/view'` | `'/<int:ref_num>/view'` |
| 406 | `'/<ref_num>/unlock'` | `'/<int:ref_num>/unlock'` |
| 425 | `'/<ref_num>/delete'` | `'/<int:ref_num>/delete'` |
| 442 | `'/short/<ref_num>/edit'` | `'/short/<int:ref_num>/edit'` |
| 534 | `'/short/<ref_num>/view'` | `'/short/<int:ref_num>/view'` |
| 571 | `'/short/<ref_num>/unlock'` | `'/short/<int:ref_num>/unlock'` |
| 590 | `'/short/<ref_num>/delete'` | `'/short/<int:ref_num>/delete'` |

- [ ] **Step 7: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe scripts/verify_route_converters.py`

Expected: exit code 0, with
```
untyped ref rules remaining: 0
GET /term-sheet/abc/view          -> 404
GET /term-sheet/edit/abc          -> 404
GET /term-sheet/abc/xyz/delete    -> 404
GET /trades/abc/edit              -> 404
GET /trades/short/abc/edit        -> 404
GET /dividends/edit/abc           -> 404
GET /fixings/abc/edit             -> 404
PASS
```

- [ ] **Step 8: Confirm every converted route still resolves for a real ref**

This is the task's one real regression risk — a route reached with a non-integer ref by a path this audit missed would now 404. Check that `url_for` still builds a URL for every converted endpoint:

```bash
./.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.')
from ltv_app import create_app
from flask import url_for
app = create_app()
ENDPOINTS = [
    ('dividends.edit', 'ref_num'), ('dividends.delete', 'ref_num'),
    ('fixings.edit', 'ref_num'), ('fixings.delete', 'ref_num'), ('fixings.unlock', 'ref_num'),
    ('term_sheet.edit', 'contract_ref'), ('term_sheet.contract_data', 'contract_ref'),
    ('term_sheet.view', 'contract_ref'), ('term_sheet.lock_contract', 'contract_ref'),
    ('term_sheet.unlock', 'contract_ref'), ('term_sheet.delete_contract', 'contract_ref'),
    ('term_sheet.set_inactive', 'contract_ref'), ('term_sheet.set_active', 'contract_ref'),
    ('term_sheet.add_line', 'contract_ref'),
    ('transactions.edit', 'ref_num'), ('transactions.view', 'ref_num'),
    ('transactions.unlock', 'ref_num'), ('transactions.delete', 'ref_num'),
    ('transactions.edit_short', 'ref_num'), ('transactions.view_short', 'ref_num'),
    ('transactions.unlock_short', 'ref_num'), ('transactions.delete_short', 'ref_num'),
]
with app.test_request_context():
    for endpoint, arg in ENDPOINTS:
        print(f'{endpoint:32} {url_for(endpoint, **{arg: 7})}')
    print('term_sheet.delete_period        ',
          url_for('term_sheet.delete_period', contract_ref=7, period_ref=3))
"
```

Expected: 23 lines, every URL containing `7` (and `7/3` for the last), no `BuildError`.

- [ ] **Step 9: Commit**

```bash
git add ltv_app/blueprints/dividends/views.py ltv_app/blueprints/fixings/views.py ltv_app/blueprints/term_sheet/views.py ltv_app/blueprints/transactions/views.py scripts/verify_route_converters.py
git commit -m "fix: type ref_num/contract_ref/period_ref route converters as int"
```

---

## Task 4: Set `SameSite=Lax` on the session cookie

**Files:**
- Modify: `server/ltv_app/__init__.py:45-53` (the `from_mapping` block Task 1 also touches)
- Test: `server/scripts/verify_session_cookie.py`

**Interfaces:**
- Consumes: `instance/config.py` from Task 1 — the PythonAnywhere copy of that file gains `SESSION_COOKIE_SECURE = True` in Step 5 here.
- Produces: no code interface. Config keys only.

- [ ] **Step 1: Write the failing test**

Create `server/scripts/verify_session_cookie.py`:

```python
"""Verification of session cookie attributes.

SESSION_COOKIE_SECURE is deliberately NOT set in code -- it would stop the
cookie being sent over http://127.0.0.1:5001 and break local dev login. It is
set in PythonAnywhere's instance/config.py instead, so this script expects it
to be False locally and does not fail on that.

SameSite matters more than usual here: no CSRFProtect is registered in
create_app(), so Lax is the only barrier to a cross-site state-changing POST.

Run: server/.venv/Scripts/python.exe scripts/verify_session_cookie.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from flask import session

from ltv_app import create_app

app = create_app()


@app.route("/__cookie_probe")
def _cookie_probe():
    """Local-only probe route -- writes to the session so a cookie is issued.

    Registered on this script's app instance only, never on the real app.
    """
    session["probe"] = 1
    return "ok"


failures = []

samesite = app.config["SESSION_COOKIE_SAMESITE"]
httponly = app.config["SESSION_COOKIE_HTTPONLY"]
secure = app.config["SESSION_COOKIE_SECURE"]

print(f"SESSION_COOKIE_SAMESITE : {samesite!r}")
print(f"SESSION_COOKIE_HTTPONLY : {httponly}")
print(f"SESSION_COOKIE_SECURE   : {secure}  (expected False locally)")

if samesite != "Lax":
    failures.append(f"SESSION_COOKIE_SAMESITE is {samesite!r}, expected 'Lax'")
if not httponly:
    failures.append("SESSION_COOKIE_HTTPONLY is not True")
if secure:
    failures.append("SESSION_COOKIE_SECURE is True locally -- this breaks "
                    "login over http://127.0.0.1:5001; set it only on PythonAnywhere")

header = app.test_client().get("/__cookie_probe").headers.get("Set-Cookie", "")
print(f"Set-Cookie              : {header}")

if "SameSite=Lax" not in header:
    failures.append("Set-Cookie lacks SameSite=Lax")
if "HttpOnly" not in header:
    failures.append("Set-Cookie lacks HttpOnly")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./.venv/Scripts/python.exe scripts/verify_session_cookie.py`

Expected: exit code 1, with
```
SESSION_COOKIE_SAMESITE : None
FAIL: SESSION_COOKIE_SAMESITE is None, expected 'Lax'
FAIL: Set-Cookie lacks SameSite=Lax
```

- [ ] **Step 3: Add the config key**

In `server/ltv_app/__init__.py`, add `SESSION_COOKIE_SAMESITE` to the existing `from_mapping` call so the block reads:

```python
    app.config.from_mapping(
        # Random per-process fallback so a fresh clone still boots without a
        # committed secret. Overridden below by instance/config.py (untracked).
        # NOTE: the app is built with instance_relative_config=True, so
        # from_pyfile('config.py') resolves against instance_path -- the file
        # must be at instance/config.py, NOT the server/ root.
        SECRET_KEY=secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "LTV Stocks.db"),
        # No CSRFProtect is registered, so SameSite is the only thing stopping a
        # cross-site state-changing POST. SESSION_COOKIE_SECURE is deliberately
        # left False here and set to True in PythonAnywhere's instance/config.py
        # -- setting it in code would break login over local plain HTTP.
        SESSION_COOKIE_SAMESITE="Lax",
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe scripts/verify_session_cookie.py`

Expected: exit code 0, with `SESSION_COOKIE_SAMESITE : 'Lax'`, a `Set-Cookie` header containing both `SameSite=Lax` and `HttpOnly`, and `PASS`.

- [ ] **Step 5: Confirm local login still works**

Start the app (`./.venv/Scripts/python.exe flask_app.py`), log in at `http://127.0.0.1:5001`, navigate to two pages, and confirm the session persists. `SameSite=Lax` permits same-site forms and top-level GET navigation, so this should be unaffected — but it is the one change that could plausibly break sign-in, so verify it by hand rather than assuming. Stop the server afterwards.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/__init__.py scripts/verify_session_cookie.py
git commit -m "fix: set SameSite=Lax on the session cookie"
```

- [ ] **Step 7: Set `SESSION_COOKIE_SECURE` on PythonAnywhere**

Append to `/home/larrylilia/ltv_app/instance/config.py` (the file created in Task 1, Step 9):

```python
SESSION_COOKIE_SECURE = True
```

Then `git pull` and reload the web app. Confirm in the browser's dev tools that the session cookie on `larrylilia.pythonanywhere.com` carries `Secure`, `HttpOnly`, and `SameSite=Lax`, and that login still works.

---

## Self-Review

Checked against `docs/superpowers/specs/2026-08-15-secret-key-and-session-hardening-design.md`:

- **Item 1 (SECRET_KEY)** → Task 1, including the `instance/` vs `server/` path correction, the gitignore pre-check, and the required PythonAnywhere step.
- **Item 2 (`save()` interpolation)** → Task 2, with the plain-INTEGER case that actually reproduces the bug plus a positive test that normal updates still touch exactly one row.
- **Item 3 (route converters)** → Task 3, all 23 decorators / 24 params enumerated by exact line, `<source>` explicitly excluded, `url_for` regression check included.
- **Item 4 (SameSite)** → Task 4, with `SESSION_COOKIE_SECURE` kept out of code and pushed to PA config, and the inert `PERMANENT_SESSION_LIFETIME` left alone per the spec.
- **Non-goals** — no task adds `CSRFProtect`, sweeps for further SQL paths, or touches password handling.

Naming is consistent across tasks: `instance/config.py` throughout (never `server/config.py` except where quoting the superseded 2026-07-17 instruction), `Model.save()`, and the four `scripts/verify_*.py` names as listed in File Structure.

## Execution Handoff

Tasks 1-4 are independent and may be executed and reviewed in any order, though the listed order puts the user-visible fix first. Tasks 1 and 4 each end with a PythonAnywhere step; those two server visits can be combined into one at the end.
