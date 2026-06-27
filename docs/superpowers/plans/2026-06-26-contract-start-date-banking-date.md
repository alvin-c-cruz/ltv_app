# Contract Start Date → Banking Date Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the **Add Contract** modal's Start Date auto-fill to the next banking day after Trade Date, skipping weekends and the selected stock's currency holidays.

**Architecture:** Front-end-only change. Reuse the existing currency-aware endpoint `GET /trades/api/next-banking-day` (already used by the Spot/Short value-date fields) from the Add Contract modal's JavaScript. Add a pytest regression test that locks the endpoint's `days=1` banking-day behaviour. No backend or schema changes.

**Tech Stack:** Flask, Jinja2 templates, vanilla JavaScript (`fetch`), pytest functional tests, SQLite.

## Global Constraints

- Work only within `ltv_app/`. Do not modify `localhost/`, `pricing/`, or `app.py`.
- No database schema or model changes (this feature needs none).
- Scope is the **Add Contract modal (`contractModal`) only**. Do not touch the Edit Contract modal (`editContractModal`, opened by `openEditContractModal()`).
- The next-banking-day endpoint lives at `/trades/api/next-banking-day` and returns JSON `{"value_date": "YYYY-MM-DD"}`.
- Spec: `docs/superpowers/specs/2026-06-26-contract-start-date-banking-date-design.md`.

---

### Task 1: Regression test for the next-banking-day endpoint (days=1)

Locks the server behaviour the Start Date field relies on: advancing one banking day, skipping weekends and the stock currency's holidays. The endpoint (`ltv_app/blueprints/transactions/views.py:782`, `next_banking_day`) already exists, so these tests pass against current code — they are characterization/regression coverage, not red-first TDD.

**Files:**
- Test: `tests/functional/test_next_banking_day.py` (create)

**Interfaces:**
- Consumes: `GET /trades/api/next-banking-day?code_ref=<id>&trade_date=<YYYY-MM-DD>&days=<n>` → `{"value_date": "YYYY-MM-DD"}`. Fixtures `auth_client`, `db_conn` from `tests/functional/conftest.py`. Seeded stock code `700` has `ref_num=1`, `ccy_ref=1` (HKD).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Write the tests**

```python
"""Regression tests for the currency-aware next-banking-day endpoint."""
import json


def _next(auth_client, code_ref, trade_date, days=1):
    resp = auth_client.get(
        f'/trades/api/next-banking-day?code_ref={code_ref}'
        f'&trade_date={trade_date}&days={days}'
    )
    assert resp.status_code == 200
    return json.loads(resp.data)['value_date']


def test_one_banking_day_normal_weekday(auth_client):
    # 2026-06-29 is a Monday; +1 banking day -> Tuesday 2026-06-30
    assert _next(auth_client, 1, '2026-06-29') == '2026-06-30'


def test_one_banking_day_skips_weekend(auth_client):
    # 2026-07-03 is a Friday; +1 banking day -> Monday 2026-07-06
    assert _next(auth_client, 1, '2026-07-03') == '2026-07-06'


def test_one_banking_day_skips_currency_holiday(auth_client, db_conn):
    # Seed a HKD (ccy_ref=1) holiday on Tue 2026-06-30.
    db_conn.execute(
        "INSERT INTO tbl_holiday (holi_date, ccy_ref) VALUES ('2026-06-30', 1)"
    )
    db_conn.commit()
    # From Mon 2026-06-29, +1 banking day skips the holiday -> Wed 2026-07-01
    assert _next(auth_client, 1, '2026-06-29') == '2026-07-01'
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/functional/test_next_banking_day.py -v`
Expected: 3 passed. (If `test_one_banking_day_skips_currency_holiday` fails, the endpoint is not filtering holidays by `ccy_ref` — stop and investigate before proceeding.)

- [ ] **Step 3: Commit**

```bash
git add tests/functional/test_next_banking_day.py
git commit -m "test: lock next-banking-day endpoint days=1 behaviour"
```

---

### Task 2: Wire Start Date to the banking-day endpoint in the Add Contract modal

Replace the naive "Trade Date + 1 calendar day" auto-fill with a currency-aware banking-day computation, recomputed on stock change and trade-date change.

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html` (JavaScript block starting ~line 716)

**Interfaces:**
- Consumes: the endpoint from Task 1; existing helper `addBusinessDays(dateStr, days)` (home.html ~line 720); the Add Contract modal's `.modal-start-date` input (`name="start_date"`, home.html:519), `select[name="code_ref"]`, and `input[name="trade_date"]`.
- Produces: nothing consumed by later tasks.

There is no JavaScript unit-test harness in this repo, so this task is verified manually against the running app. Make the edits, then run the verification checklist before committing.

- [ ] **Step 1: Add the `updateStartDate` function**

In `home.html`, immediately after the existing `updateValueDate(modal)` function (it ends ~line 755, just before `function openTxnModal(id)`), insert:

```javascript
function updateStartDate(modal) {
    var startDateInput = modal.querySelector('.modal-start-date');
    if (!startDateInput) return;  // only the Add Contract modal has this field

    var stockSelect = modal.querySelector('select[name="code_ref"]');
    var tradeDateInput = modal.querySelector('input[name="trade_date"]');
    if (!tradeDateInput) return;

    var codeRef = stockSelect ? stockSelect.value : '';
    var tradeDate = tradeDateInput.value;

    if (codeRef && tradeDate) {
        fetch('/trades/api/next-banking-day?code_ref=' + codeRef + '&trade_date=' + tradeDate + '&days=1')
            .then(function(r){ return r.json(); })
            .then(function(data){ if (data.value_date) startDateInput.value = data.value_date; })
            .catch(function(err){ console.error('Error calculating start date:', err); });
    } else if (tradeDate) {
        startDateInput.value = addBusinessDays(tradeDate, 1);
    }
}
```

- [ ] **Step 2: Update `openTxnModal` to use banking-day Start Date**

Replace the current `openTxnModal` body (home.html ~lines 757–782) so the Start Date uses a weekend-only fallback on open, recomputes on stock/trade-date change, and refines via the endpoint. The full replacement:

```javascript
function openTxnModal(id) {
    var m = document.getElementById(id);
    m.querySelectorAll('.modal-date').forEach(function(el){ el.value = _today; });
    // Start Date: weekend-only fallback now; refined to a banking day below.
    m.querySelectorAll('.modal-start-date').forEach(function(el){ el.value = addBusinessDays(_today, 1); });

    // Set up listeners for stock and trade date changes
    var stockSelect = m.querySelector('select[name="code_ref"]');
    var tradeDateInput = m.querySelector('input[name="trade_date"]');

    if (stockSelect) {
        stockSelect.addEventListener('change', function(){ updateValueDate(m); updateStartDate(m); });
    }
    if (tradeDateInput) {
        tradeDateInput.addEventListener('change', function(){ updateValueDate(m); updateStartDate(m); });
    }

    // Default value date: T+2 business days from trade date
    m.querySelectorAll('.modal-value-date').forEach(function(el){ el.value = addBusinessDays(_today, 2); });

    // Refine with holiday data if stock is already selected
    if (stockSelect && stockSelect.value) {
        updateValueDate(m);
    }
    // Refine Start Date (no-op for modals without a .modal-start-date field)
    updateStartDate(m);

    m.classList.add('active');
}
```

- [ ] **Step 3: Remove the now-unused `_sdStr` variable**

The static calendar+1 value is no longer used. Delete this line (home.html ~line 718):

```javascript
var _sdStr = (function(){ var d=new Date(_today); d.setDate(d.getDate()+1); return d.toISOString().slice(0,10); })();
```

Leave `var _today = '{{ trade_date }}';` (still used). Confirm `_sdStr` has no other references: `grep -n "_sdStr" ltv_app/blueprints/transactions/pages/transactions/home.html` should return nothing.

- [ ] **Step 4: Manual verification against the running app**

Start the app: `python flask_app.py` (serves on the printed `http://<ip>:5001`). Log in, open `/trades/`, click **+ Contract**, and verify (Trade Date defaults to today; pick HKD stocks):

1. Select an HKD stock, set Trade Date to a Friday → Start Date becomes the following Monday (or next banking day).
2. Set Trade Date to a normal weekday with no holiday next day → Start Date = Trade Date + 1.
3. Set Trade Date to **2026-06-29** with stock that is HKD → Start Date = **2026-06-30** (no holiday there now); set Trade Date to the day before a known 2027 HK holiday (e.g. **2027-04-02**, a Friday before Ching Ming Mon 2027-04-05) → Start Date skips to the next banking day after the holiday.
4. Change the selected stock → Start Date recomputes.
5. Change the Trade Date → Start Date recomputes.
6. Open **+ Spot** / **+ Short** → their value-date behaviour is unchanged and no console errors appear (confirms `updateStartDate`'s early return is harmless for modals without a Start Date field).
7. Click **Edit** on an existing contract → its saved Start Date is unchanged.

Record the result of each check. If any check fails, fix the JS and re-verify before committing.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/transactions/pages/transactions/home.html
git commit -m "feat(contract): compute Add Contract Start Date as next banking day"
```

---

## Self-Review

- **Spec coverage:** Rule = next banking day after Trade Date (Task 2 `days=1`, fallback `addBusinessDays(_, 1)`); currency-aware via stock `code_ref` (endpoint reuse, Task 1 holiday test); recompute on stock/trade-date change (Task 2 listeners); Add-modal-only, Edit untouched (Task 2 Step 4 check 7, scoped via `.modal-start-date` which only `contractModal` has); no backend/schema change (confirmed). Known-limitation (non-HKD stale holidays) is documented in the spec and not in scope. Covered.
- **Placeholder scan:** No TBD/TODO; all code blocks complete; verification steps concrete with dated examples.
- **Type/name consistency:** `updateStartDate`, `addBusinessDays`, `.modal-start-date`, `code_ref`, `trade_date`, response key `value_date` used consistently across tasks and match the existing code.
