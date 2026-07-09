# Term Sheet Undo-KO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Set Active (undo KO)" item to the term-sheet right-click menu that reverts a contract from `status='KO'` back to `status='active'`.

**Architecture:** A new `POST /term-sheet/<contract_ref>/set-active` route mirrors the existing `set_inactive` route in guard order and response shape. The context menu gains a second item, shown only when the right-clicked row's raw `data-status` is `KO`. One column write; no schema change.

**Tech Stack:** Python 3, Flask, Flask-Login, SQLite, Jinja2, vanilla JS `fetch`, pytest.

**Spec:** `docs/superpowers/specs/2026-07-09-term-sheet-undo-ko-design.md` (commit `ea9180f`)

## Global Constraints

- **Live production database.** `instance/LTV Stocks.db` holds real financial data. No task in this plan may write to it. Tests use the isolated temp SQLite from `tests/functional/conftest.py`; browser verification uses a separate seeded temp database (Task 3).
- **Blueprint path is `applications/ltv_app/blueprints/term_sheet/`** — note the `applications/` prefix. There is no top-level `ltv_app/` in the working tree.
- **The Python import name is still top-level `ltv_app`, not `applications.ltv_app`.** `pytest.ini` sets `pythonpath = applications`, and `flask_app.py` / `conftest.py` insert `applications/` on `sys.path`. Import as `from ltv_app... import ...`.
- **Work happens on branch `term-sheet-undo-ko`.** The `applications/` rename and its import/instance/`.gitignore` fixups are already committed (`531fd8a`, `08013f7`) on `main`; the tree is clean with respect to them.
- **Do not commit `tests/functional/test_notebook_transfers.py`.** The working tree holds a pre-existing, uncommitted deletion of `test_transfer_opening_follows_prior_same_day_transfer` that belongs to the user, not to this feature. Leave it exactly as found; pass explicit pathspecs after `--` on every commit so it is never swept in.
- **Known-failing baseline** (pre-existing, not caused by this work): 11 tests in `tests/functional/test_download_trades_done.py::OldTradesDoneTests` and `tests/functional/test_gmail.py::test_inbox_superuser_shows_threads`. `tests/ltv2/` does not collect (`ModuleNotFoundError: argon2`). Baseline for `pytest tests/functional tests/unit` is **12 failed, 227 passed, 2 skipped**. A regression means a test outside that set starts failing.
- **Permission rule, copied from `set_inactive`:** `@login_required`; a `locked` contract returns 403 unless `current_user.role == 'superuser'`.
- **Precondition:** only `status == 'KO'` may be set active. `DONE` is a *display* value and must never be used as the gate.
- **Guard order:** existence (404) → lock/permission (403) → precondition (400) → write.
- **Do not modify** the existing `set_inactive` route or its `{{ url_for(...) }}/../` fetch URL. Out of scope by decision.

---

### Task 1: The `set_active` route

**Files:**
- Modify: `applications/ltv_app/blueprints/term_sheet/views.py` (insert after line 421, the end of `set_inactive`)
- Test: `tests/functional/test_term_sheet_set_active.py` (create)

**Interfaces:**
- Consumes: `get_db()` (already imported in `views.py`), `login_required` (already imported from `..auth`), `jsonify`, `current_user` — all already imported at the top of `views.py`. No new imports.
- Produces: Flask endpoint `term_sheet.set_active`, URL rule `/<contract_ref>/set-active`, methods `["POST"]`. Task 2 references this endpoint by name in `url_for`.

Response contract, matching `set_inactive`:

| Condition | Status | Body |
|---|---|---|
| no such `ref_num` | 404 | `{"success": false, "message": "Contract not found"}` |
| `locked` and not superuser | 403 | `{"success": false, "message": "Contract is locked and cannot be modified"}` |
| `status != 'KO'` | 400 | `{"success": false, "message": "Only contracts with KO status can be set back to active"}` |
| otherwise | 200 | `{"success": true, "message": "Contract status updated to active"}` |

Fixtures used, from `tests/functional/conftest.py`: `superuser_client` (user `super_user`, role `superuser`), `auth_client` (user `staff_user`, role `staff`), `db_conn` (row_factory `sqlite3.Row`). The conftest creates `tbl_stock_contract` and `tbl_stock_contract_period` but seeds **no contract rows**; seeded reference rows are `bank_ref=1` (`CB1`), `code_ref=1` (stock `700`).

- [ ] **Step 1: Write the failing test**

Create `tests/functional/test_term_sheet_set_active.py`:

```python
import pytest


def _insert_contract(db_conn, ref_num, status, locked=0):
    """Insert one ACCU contract. Returns ref_num."""
    db_conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status, reviewed, locked) "
        "VALUES (?, ?, 1, 1, '2026-01-02', '2026-01-05', 'ACCU', 1000, 'No', "
        "        100.0, 90.0, 105.0, '3m', 'monthly', 'No', NULL, ?, 0, ?)",
        (ref_num, f"Tencent - {ref_num}", status, locked),
    )
    db_conn.commit()
    return ref_num


def _insert_periods(db_conn, contract_ref, count, received):
    """Insert `count` periods. `received` is '' (open) or a share count string."""
    for i in range(count):
        db_conn.execute(
            "INSERT INTO tbl_stock_contract_period "
            "(contract_ref, start_date, end_date, days, received, gtd) "
            "VALUES (?, ?, ?, '20', ?, 'No')",
            (contract_ref, f"2026-0{i + 1}-05", f"2026-0{i + 1}-28", received),
        )
    db_conn.commit()


def _status_of(db_conn, ref_num):
    return db_conn.execute(
        "SELECT status FROM tbl_stock_contract WHERE ref_num=?", (ref_num,)
    ).fetchone()["status"]


def test_superuser_reverts_ko_to_active(superuser_client, db_conn):
    _insert_contract(db_conn, 900, status="KO", locked=1)

    resp = superuser_client.post("/term-sheet/900/set-active")

    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    assert _status_of(db_conn, 900) == "active"


def test_non_superuser_blocked_on_locked_contract(auth_client, db_conn):
    _insert_contract(db_conn, 901, status="KO", locked=1)

    resp = auth_client.post("/term-sheet/901/set-active")

    assert resp.status_code == 403
    assert resp.get_json()["success"] is False
    assert _status_of(db_conn, 901) == "KO"  # nothing was written


def test_non_ko_contract_rejected(superuser_client, db_conn):
    _insert_contract(db_conn, 902, status="active", locked=0)

    resp = superuser_client.post("/term-sheet/902/set-active")

    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
    assert _status_of(db_conn, 902) == "active"  # nothing was written


def test_unknown_contract_returns_404(superuser_client):
    resp = superuser_client.post("/term-sheet/99999/set-active")

    assert resp.status_code == 404
    assert resp.get_json()["success"] is False


def test_ko_contract_that_is_also_done_can_be_reverted(superuser_client, db_conn):
    """A KO contract whose periods are all received renders as DONE, not KO
    (models.py:163 checks next_date before status). The route must gate on
    `status`, not on the displayed value, so this must still succeed."""
    _insert_contract(db_conn, 903, status="KO", locked=1)
    _insert_periods(db_conn, 903, count=3, received="20000")

    resp = superuser_client.post("/term-sheet/903/set-active")

    assert resp.status_code == 200
    assert _status_of(db_conn, 903) == "active"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/functional/test_term_sheet_set_active.py -v`

Expected: all 5 FAIL. The route does not exist, so Flask returns 404 for every POST. Four tests fail on the status-code assertion; `test_unknown_contract_returns_404` fails later, on `resp.get_json()` returning `None` (the 404 is Flask's HTML error page, not our JSON). That distinction matters — it proves the 404 test is not passing for the wrong reason.

- [ ] **Step 3: Write the implementation**

In `applications/ltv_app/blueprints/term_sheet/views.py`, insert after line 421 (the `return` that ends `set_inactive`) and before the `@bp.route("/<bank_id>/<transaction_type>/<code>")` rule:

```python
@bp.route("/<contract_ref>/set-active", methods=["POST"])
@login_required
def set_active(contract_ref):
    db = get_db()

    # Check if contract exists and get its current status
    row = db.execute("SELECT status, locked FROM tbl_stock_contract WHERE ref_num=?", (contract_ref,)).fetchone()

    if not row:
        return jsonify({"success": False, "message": "Contract not found"}), 404

    if row['locked'] and current_user.role != 'superuser':
        return jsonify({"success": False, "message": "Contract is locked and cannot be modified"}), 403

    # Gate on the stored status, never on the displayed "DONE" value: a KO
    # contract with all periods received renders as DONE (models.py:163).
    if row['status'] != 'KO':
        return jsonify({"success": False, "message": "Only contracts with KO status can be set back to active"}), 400

    # Update status to active
    db.execute("UPDATE tbl_stock_contract SET status='active' WHERE ref_num=?", (contract_ref,))
    db.commit()

    return jsonify({"success": True, "message": "Contract status updated to active"})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/functional/test_term_sheet_set_active.py -v`

Expected: `5 passed`.

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `python -m pytest -q tests/functional tests/unit`

Expected: **12 failed, 227 passed + 5 new = 232 passed, 2 skipped.** The 12 failures are the known-failing baseline listed in Global Constraints and must be exactly that set — 11 in `test_download_trades_done.py::OldTradesDoneTests` plus `test_gmail.py::test_inbox_superuser_shows_threads`. Any *other* test failing is a regression you introduced; fix it before committing.

Do not run bare `pytest` — it collects `tests/ltv2/`, which errors out on a missing `argon2` module unrelated to this work.

- [ ] **Step 6: Commit**

```bash
git add -- applications/ltv_app/blueprints/term_sheet/views.py tests/functional/test_term_sheet_set_active.py
git commit -m "feat(term-sheet): add set-active route to undo a KO"
```

---

### Task 2: The context-menu item

**Files:**
- Modify: `applications/ltv_app/blueprints/term_sheet/pages/term_sheet/home.html` (row `<tr>` at line 45; menu `<div>` at lines 108-113; script at lines 115-171)

**Interfaces:**
- Consumes: endpoint `term_sheet.set_active` from Task 1, via `url_for('term_sheet.set_active', contract_ref=accu.ref_num)`.
- Produces: no interface for later tasks. Task 3 drives this UI.

The row already carries `data-contract-ref`, `data-status` (raw `self.status`, `models.py:187`) and `data-next-date` (the *display* value). Read the URL from a new `data-set-active-url` attribute rather than reconstructing it, so the endpoint stays authoritative.

- [ ] **Step 1: Add the URL to each row**

In `home.html` line 45, extend the `<tr>` with one attribute. The line becomes:

```html
<tr class="clickable-row" data-href="{{ url_for('term_sheet.edit', contract_ref=accu.ref_num) }}" data-contract-ref="{{ accu.ref_num }}" data-status="{{ accu.status }}" data-next-date="{{ accu.next_date }}" data-set-active-url="{{ url_for('term_sheet.set_active', contract_ref=accu.ref_num) }}"
```

Leave the `{% if accu.next_date == 'KO' %}style=...` continuation on the next line untouched.

- [ ] **Step 2: Add the menu item**

Replace the context-menu `<div>` at lines 108-113 with:

```html
<!-- Context Menu -->
<div id="contextMenu" style="display: none; position: absolute; background: white; border: 1px solid #ccc; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000;">
    <div id="setInactiveOption" style="padding: 10px 15px; cursor: pointer; border-bottom: 1px solid #eee;">
        Set Inactive
    </div>
    <div id="setActiveOption" style="display: none; padding: 10px 15px; cursor: pointer;">
        Set Active (undo KO)
    </div>
</div>
```

- [ ] **Step 3: Wire up visibility and the click handler**

In the `<script>` block, add the element lookup and URL variable beside the existing ones (lines 117-119):

```javascript
    const contextMenu = document.getElementById('contextMenu');
    const setInactiveOption = document.getElementById('setInactiveOption');
    const setActiveOption = document.getElementById('setActiveOption');
    let currentContractRef = null;
    let currentSetActiveUrl = null;
```

Inside the `contextmenu` listener, within the existing `if (status === 'KO' || nextDate === 'DONE') {` block, after `currentContractRef = ...` (line 130), add:

```javascript
                currentSetActiveUrl = this.getAttribute('data-set-active-url');

                // Undoing a KO only means something for a stored status of KO.
                // A DONE row is already active, so hide the item there.
                setActiveOption.style.display = (status === 'KO') ? 'block' : 'none';
```

After the existing `setInactiveOption` click handler (after line 164), add:

```javascript
    // Handle clicking "Set Active (undo KO)"
    setActiveOption.addEventListener('click', function() {
        if (currentSetActiveUrl) {
            if (confirm('Undo the KO on this contract? It will become active again and will resume appearing in fixings, HKD margin, block/unblock and DECU positions.')) {
                fetch(currentSetActiveUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Error: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('An error occurred: ' + error);
                });
            }
        }
        contextMenu.style.display = 'none';
    });
```

The confirm text names the four consumers the revert re-enables (spec, "What `status='active'` re-enables"). This is a consequential write behind one click; the generic "Are you sure?" used by Set Inactive would undersell it.

- [ ] **Step 4: Verify the template still renders**

The dev server auto-reloads. With the server running (see Task 3 for how it binds), fetch the page as an authenticated user and confirm HTTP 200 plus the new markup:

Run:
```bash
python .claude/skills/run-ltv-app/driver.py
```
Expected: `ALL PASS`. This proves the template compiles — a Jinja syntax error or an unknown endpoint in `url_for` would make `GET /term-sheet/...` raise, and a broken template anywhere would surface as a 500 on the routes the driver walks.

- [ ] **Step 5: Commit**

```bash
git add -- applications/ltv_app/blueprints/term_sheet/pages/term_sheet/home.html
git commit -m "feat(term-sheet): add 'Set Active (undo KO)' context menu item"
```

---

### Task 3: Browser verification against a seeded database

**Files:**
- Create: `<scratchpad>/serve_seeded.py` (throwaway; not committed)

**Interfaces:**
- Consumes: `create_app` from `applications.ltv_app`, `_SCHEMA` and `_seed` from `tests.functional.conftest`.
- Produces: nothing. This task is verification only.

`flask_app.py` binds `create_app()` to the **production** database. Never drive the new menu item against it — the 6 real KO contracts are production financial records. Instead run a second app instance, on a different port, against a temp database seeded with a KO contract.

- [ ] **Step 1: Write the seeded server script**

Create `<scratchpad>/serve_seeded.py`:

```python
"""Serve the LTV app on :5002 against a throwaway seeded database."""
import sqlite3
import sys
import tempfile
from pathlib import Path

_SERVER = r"C:\envs\LTV\server"
sys.path.insert(0, _SERVER)                       # for tests.functional.conftest
sys.path.insert(0, _SERVER + r"\applications")    # ltv_app is imported top-level

from tests.functional.conftest import _SCHEMA, _seed
from ltv_app import create_app

db_path = Path(tempfile.mkdtemp()) / "seeded.db"
conn = sqlite3.connect(str(db_path))
conn.executescript(_SCHEMA)
_seed(conn)

# One KO contract on bank CB1 (bank_ref=1), stock 700 (code_ref=1), unlocked
# so a plain login can drive it.
conn.execute(
    "INSERT INTO tbl_stock_contract "
    "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
    " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
    " tenor, frequency, gtd, bank_doc, status, reviewed, locked) "
    "VALUES (900, 'Tencent - KO test', 1, 1, '2026-01-02', '2026-01-05', 'ACCU', "
    "        1000, 'No', 100.0, 90.0, 105.0, '3m', 'monthly', 'No', NULL, 'KO', 0, 0)"
)
for i in range(3):
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (900, ?, ?, '20', '', 'No')",
        (f"2026-0{i + 1}-05", f"2026-0{i + 1}-28"),
    )
conn.commit()
conn.close()

print(f"seeded db: {db_path}")
app = create_app({"DATABASE": str(db_path), "SECRET_KEY": "verify-secret"})
app.run(host="127.0.0.1", port=5002, debug=False)
```

This instance binds `127.0.0.1` deliberately, unlike `flask_app.py` which binds the LAN IP from `socket.gethostbyname(socket.gethostname())`.

- [ ] **Step 2: Start it in the background**

Run: `python <scratchpad>/serve_seeded.py` as a background process.
Expected: prints `seeded db: ...` then `Running on http://127.0.0.1:5002`.

- [ ] **Step 3: Drive the menu with Playwright**

Playwright's Python package is installed. If `playwright._impl._errors.Error: Executable doesn't exist` appears, run `python -m playwright install chromium` once.

The page uses `confirm()`. A dialog handler MUST be registered **before** the click, or the click blocks forever. Create `<scratchpad>/drive_menu.py`:

```python
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5002"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("dialog", lambda d: d.accept())   # register BEFORE any click

    page.goto(f"{BASE}/login")
    page.fill("input[name=username]", "super_user")
    page.fill("input[name=password]", "superpass")
    page.click("button[type=submit]")
    page.wait_for_load_state()

    page.goto(f"{BASE}/term-sheet/CB1")
    row = page.locator("tr.clickable-row[data-status='KO']")
    assert row.count() == 1, f"expected 1 KO row, found {row.count()}"

    row.click(button="right")
    page.wait_for_selector("#contextMenu", state="visible")
    page.screenshot(path="menu-open.png")

    inactive = page.locator("#setInactiveOption")
    active = page.locator("#setActiveOption")
    assert inactive.is_visible(), "Set Inactive should be visible on a KO row"
    assert active.is_visible(), "Set Active should be visible on a KO row"
    print("menu OK: both items visible")

    active.click()                     # confirm() auto-accepted by the handler
    page.wait_for_load_state("load")
    page.screenshot(path="after-revert.png")

    assert page.locator("tr.clickable-row[data-status='KO']").count() == 0, \
        "row should no longer be KO after revert"
    print("revert OK: no KO row remains")
    browser.close()
```

Run: `python <scratchpad>/drive_menu.py`
Expected: `menu OK: both items visible` then `revert OK: no KO row remains`.

**Read `menu-open.png` with the Read tool and look at it.** Expected: a two-item menu reading `Set Inactive` and `Set Active (undo KO)`. One item means the visibility toggle never ran. A blank image means the page failed to render — the assertions above would not catch that.

- [ ] **Step 4: Confirm the row is gone from KO styling and the DB changed**

After reload the row must no longer carry the red KO background (`home.html:46` keys that off `accu.next_date == 'KO'`). Then read the seeded database back:

```bash
python -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('SELECT status FROM tbl_stock_contract WHERE ref_num=900').fetchone())" "<seeded db path printed in Step 2>"
```
Expected: `('active',)`

- [ ] **Step 5: Confirm the item is hidden on a non-KO row**

Right-click the same row again, now that it is `active`. Expected: the menu does not open at all — the outer `if (status === 'KO' || nextDate === 'DONE')` gate is false for an active row with open periods. This confirms we did not widen when the menu appears.

- [ ] **Step 6: Stop the seeded server**

Kill the background process. Nothing to commit — the script is a throwaway and lives in the scratchpad, outside the repo.

---

## Self-Review

**Spec coverage.** Backend route → Task 1 Step 3. Guard order and the four response codes → Task 1 Steps 1/3. Frontend `data-set-active-url` and the `status === 'KO'` visibility rule → Task 2 Steps 1-3. The five test cases, including the KO-and-DONE precedence trap → Task 1 Step 1. Playwright verification against a seeded (never production) contract → Task 3. The "What `status='active'` re-enables" section is surfaced to the user in the Task 2 confirm text. The spec's two explicit non-goals — reviving `inactive` contracts, and touching `set_inactive`'s URL or test coverage — appear as Global Constraints and have no task, correctly.

**Placeholder scan.** No TBDs. Every code step carries complete code. The only bracketed value is `<scratchpad>` in Task 3, which resolves to this session's scratchpad directory, and the seeded-db path in Step 4, which Step 2 prints at runtime.

**Type consistency.** `set_active` is the endpoint name in Task 1 and in Task 2's `url_for`. `setActiveOption` and `currentSetActiveUrl` are declared in Task 2 Step 3 and used only there. `_insert_contract` / `_insert_periods` / `_status_of` are defined and used within the one test file. Column lists in the Task 1 and Task 3 `INSERT`s match `tbl_stock_contract` as declared in `tests/functional/conftest.py:110`.
