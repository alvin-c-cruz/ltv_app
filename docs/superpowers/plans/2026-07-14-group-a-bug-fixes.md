# Group A Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix five independent, low-risk bugs in `ltv_app` (Unlock 405, Fixings redirect target, missing Bank Reference indicator, unreliable Print Trades Done popup, and a stale per-row period total) per the approved design at `docs/superpowers/specs/2026-07-14-group-a-bug-fixes-design.md`.

**Architecture:** No new subsystems — each task is a targeted edit to an existing route or template, following patterns already established elsewhere in the same files (POST-form pattern from the existing Delete links, `modal-overlay` pattern from the existing `+Spot`/`+Contract` modals, the existing `updateToDecuTotals()` live-JS pattern).

**Tech Stack:** Flask 3.1 (Jinja2 templates, raw `sqlite3`), vanilla JS (no framework/bundler — inline `<script>` blocks per template), existing `main.css`.

## Global Constraints

- No test suite exists in this copy of the repo (`tests/` removed, `pytest` unused) — every task's "test" step is a manual verification pass against the locally running app, driven via Chrome browser automation, per the approved spec's Verification section.
- `server/` is a git repo with a **public** GitHub remote (`alvin-c-cruz/ltv_app`). Never put real client data (account names, contract numbers, share counts, bank references) into code, comments, or commit messages — that's why `BUGS.md` itself stays out of this repo.
- The local dev server is already running: `C:/envs/LTV-ai/server/.venv/Scripts/python.exe flask_app.py` from `server/`, bound to `http://192.168.1.48:5001`, `debug=True`. Flask's reloader restarts the process automatically on `.py` edits; Jinja auto-reloads templates in debug mode — no manual restart needed for either kind of change.
- Local login for verification: username `admin`, password `bugtest123` (set on the **local** DB copy only during the earlier reproduction session — never the production credential).
- The local DB (`server/instance/LTV Stocks.db`) is a downloaded copy of real production data. Verification steps that mutate state (e.g. clicking Unlock) are fine to run locally, but don't assume any state you change here reflects or should be pushed back to production.
- Deployment to PythonAnywhere is explicitly out of scope for this plan (per spec).

---

### Task 1: Fix Unlock 405 (GET link → POST form)

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html:88-91` (Accumulators table)
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html:143-146` (Decumulators table)

**Interfaces:**
- Consumes: existing endpoint `term_sheet.unlock` (`ltv_app/blueprints/term_sheet/views.py:347`, `methods=["POST"]` — unchanged, no route edits in this task).
- Produces: nothing consumed by other tasks in this plan.

- [ ] **Step 1: Reproduce the current 405 live**

With the local app running and logged in as `admin`/`bugtest123`, navigate to `http://192.168.1.48:5001/trades/`, pick a trade date that has a locked Accumulator or Decumulator row (locked rows show "View"/"Unlock" instead of "Edit"/"Delete"), and note its contract id from the Unlock link's `href` (`/term-sheet/<id>/unlock`). Navigate directly to that URL.

Expected: page shows "405 Method Not Allowed".

- [ ] **Step 2: Replace the Accumulators table's Unlock link**

In `ltv_app/blueprints/transactions/pages/transactions/home.html`, find:

```html
                    {% if current_user.role == 'superuser' %}
                    <a href="{{ url_for('term_sheet.unlock', contract_ref=ts.id) }}" class="btn btn-outline btn-sm"
                       onclick="return confirm('Unlock this contract?')">Unlock</a>
                    {% endif %}
```

(the first occurrence, inside the Accumulators `{% if accus %}` block, currently lines 88-91). Replace with:

```html
                    {% if current_user.role == 'superuser' %}
                    <form method="post" action="{{ url_for('term_sheet.unlock', contract_ref=ts.id) }}"
                          style="display:inline" onsubmit="return confirm('Unlock this contract?')">
                        <button type="submit" class="btn btn-outline btn-sm">Unlock</button>
                    </form>
                    {% endif %}
```

- [ ] **Step 3: Replace the Decumulators table's Unlock link**

Find the second, near-identical occurrence inside the Decumulators `{% if decus %}` block (currently lines 143-146):

```html
                    {% if current_user.role == 'superuser' %}
                    <a href="{{ url_for('term_sheet.unlock', contract_ref=ts.id) }}" class="btn btn-outline btn-sm"
                       onclick="return confirm('Unlock this contract?')">Unlock</a>
                    {% endif %}
```

Replace with the same form pattern as Step 2 (identical markup — this is the Decumulators table's copy of the same block).

- [ ] **Step 4: Verify the fix live**

Reload `http://192.168.1.48:5001/trades/` for the same trade date used in Step 1. Click the "Unlock" button on the previously-locked row (confirm the dialog). 

Expected: page redirects to `/term-sheet/edit/<id>` showing "Contract #<id> has been unlocked." — no 405.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/transactions/pages/transactions/home.html
git commit -m "fix(term-sheet): unlock via POST form instead of broken GET link"
```

---

### Task 2: Fix Fixings redirect target

**Files:**
- Modify: `ltv_app/blueprints/fixings/views.py:209-216`

**Interfaces:**
- Consumes: existing endpoint `fixings.home` (`ltv_app/blueprints/fixings/views.py:13-15`), which reads the date to display from the `trade_date` query arg on GET (falls back to `DateForm`'s default of today when absent).
- Produces: nothing consumed by other tasks in this plan.

- [ ] **Step 1: Reproduce the current wrong-redirect live**

Navigate to `http://192.168.1.48:5001/fixings/`, advance the Trade Date to a day with no fixings yet (using the `›` control until "No fixings found for `<date>`." appears with a "Record Fixings" button visible), then click "Record Fixings" (confirm the dialog).

Expected: flash message "Recorded fixings for `<that date>`." appears, but the Trade Date field and the list below it show **today's** date, not the date just recorded.

- [ ] **Step 2: Fix the redirect**

In `ltv_app/blueprints/fixings/views.py`, find:

```python
@bp.route('/record/<trade_date>')
@login_required
def record(trade_date):
    db = get_db()
    fixing_data = GenerateFixings(trade_date).fixings
    RecordFixings(db, fixing_data, trade_date)
    flash(f"Recorded fixings for {trade_date}.")
    return redirect(url_for('fixings.home'))
```

Replace the final line with:

```python
    return redirect(url_for('fixings.home', trade_date=trade_date))
```

- [ ] **Step 3: Verify the fix live**

Repeat Step 1 on a different date with no fixings yet (the previous date now has fixings recorded, so pick the next one along).

Expected: after clicking "Record Fixings", the page lands on that same date — Trade Date field and the fixings list both show the date just recorded, not today.

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/fixings/views.py
git commit -m "fix(fixings): redirect to the recorded date instead of today"
```

---

### Task 3: Add missing-Bank-Reference indicator

**Files:**
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html:168-171`
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/add.html:146-149`
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/home.html:59` and `:99`
- Modify: `ltv_app/blueprints/transactions/extensions/transaction_summary.py:194-262` (add `bank_doc` to the query, the `term_sheet(...)` construction, and the dataclass)
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html` (new "Bank Ref" column in both the Accumulators and Decumulators tables — `<thead>` at lines 67-71/122-125, row loops at lines 75-83/130-138)

**Interfaces:**
- Consumes: existing `.text-danger` CSS class (`ltv_app/static/css/main.css:389`, `color: var(--danger)`) — no new CSS needed.
- Produces: `bank_doc` field added to the `term_sheet` dataclass (`transaction_summary.py`) — not consumed elsewhere in this plan, but changes that dataclass's shape for any future code touching `TransactionSummary.accus`/`.decus`.

- [ ] **Step 1: Confirm current behavior live**

Navigate to a contract edit page for a contract with a blank Bank Reference No. (e.g. `http://192.168.1.48:5001/term-sheet/edit/1455`, confirmed blank during the earlier reproduction session). Confirm the field shows no visual difference from a filled-in field, and that the per-account Term Sheet list (`Term Sheets` dropdown → any account) and the Trades Done list render an empty cell with no indicator for that contract's reference.

- [ ] **Step 2: Add the indicator to the edit form**

In `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html`, find:

```html
            <div class="form-group">
                <label for="bank_doc">Bank Reference No.</label>
                <input type="text" name="bank_doc" id="bank_doc" value="{{ ts.bank_doc }}" autocomplete="off">
            </div>
```

Replace with:

```html
            <div class="form-group">
                <label for="bank_doc"{% if not ts.bank_doc %} class="text-danger"{% endif %}>Bank Reference No.{% if not ts.bank_doc %} (missing){% endif %}</label>
                <input type="text" name="bank_doc" id="bank_doc" value="{{ ts.bank_doc }}" autocomplete="off">
            </div>
```

- [ ] **Step 3: Add the indicator to the add form**

In `ltv_app/blueprints/term_sheet/pages/term_sheet/add.html`, find:

```html
            <div class="form-group">
                <label for="bank_doc">Bank Reference No.</label>
                <input type="text" name="bank_doc" id="bank_doc" value="{{ ts.bank_doc if ts else '' }}" autocomplete="off">
            </div>
```

Replace with (a new/blank Add form has no `ts.bank_doc` yet, so this only lights up if the form re-renders after a validation error with the field still empty):

```html
            <div class="form-group">
                <label for="bank_doc"{% if ts and not ts.bank_doc %} class="text-danger"{% endif %}>Bank Reference No.{% if ts and not ts.bank_doc %} (missing){% endif %}</label>
                <input type="text" name="bank_doc" id="bank_doc" value="{{ ts.bank_doc if ts else '' }}" autocomplete="off">
            </div>
```

- [ ] **Step 4: Add the indicator to the per-account Term Sheet list**

In `ltv_app/blueprints/term_sheet/pages/term_sheet/home.html`, find (Accumulators table, currently line 59):

```html
            <td>{{ accu.bank_doc }}</td>
```

Replace with:

```html
            <td>{% if accu.bank_doc %}{{ accu.bank_doc }}{% else %}<span class="text-danger">missing</span>{% endif %}</td>
```

Find the matching Decumulators table line (currently line 99):

```html
            <td>{{ decu.bank_doc }}</td>
```

Replace with:

```html
            <td>{% if decu.bank_doc %}{{ decu.bank_doc }}{% else %}<span class="text-danger">missing</span>{% endif %}</td>
```

- [ ] **Step 5: Add `bank_doc` to the Trades Done data source**

`transactions.home()` (`ltv_app/blueprints/transactions/views.py:15-33`) passes `accus`/`decus` from `TransactionSummary.get_term_sheets()`
(`ltv_app/blueprints/transactions/extensions/transaction_summary.py:191-245`), which does not currently select or expose `bank_doc`.

In `ltv_app/blueprints/transactions/extensions/transaction_summary.py`, find the SQL in `get_term_sheets` (lines 194-218):

```python
        sql = "SELECT " \
              " c.ref_num as contract_ref, " \
              " c.trade_date, " \
              " c.start_date, " \
              " a.bank_name, " \
              " c.transaction_type, " \
              " s.code, " \
              " s.stock_name, " \
              " c.daily_shares, " \
              " c.leveraged, " \
              " c.spot, " \
              " c.strike_rate, " \
              " c.ko_rate, " \
              " c.tenor, " \
              " c.gtd, " \
              " c.locked, " \
              " tbl_currency.ccy_id " \
```

Add `c.bank_doc` to the column list:

```python
        sql = "SELECT " \
              " c.ref_num as contract_ref, " \
              " c.trade_date, " \
              " c.start_date, " \
              " a.bank_name, " \
              " c.transaction_type, " \
              " s.code, " \
              " s.stock_name, " \
              " c.daily_shares, " \
              " c.leveraged, " \
              " c.spot, " \
              " c.strike_rate, " \
              " c.ko_rate, " \
              " c.tenor, " \
              " c.gtd, " \
              " c.locked, " \
              " c.bank_doc, " \
              " tbl_currency.ccy_id " \
```

Then find the `term_sheet(...)` construction (lines 228-242):

```python
            ts = term_sheet(
               id=row["contract_ref"],
               bank_name=row["bank_name"],
               code=row["code"],
               strike_rate=row["strike_rate"],
               ko_rate=row["ko_rate"],
               stock_name=row["stock_name"] + f" ({row['code']})",
               shares= f'{"{:,.0f}".format(row["daily_shares"])} / {"{:,.0f}".format(row["daily_shares"] * 2)}' if row["leveraged"] == "Yes" else "{:,.0f}".format(row["daily_shares"]),
               spot="{:,.4f}".format(row["spot"]),
               strike=f'{"{:,.4f}".format(row["spot"]*row["strike_rate"]/100)} ({"{:,.2f}".format(row["strike_rate"])}%)',
               ko=f'{"{:,.4f}".format(row["spot"] * row["ko_rate"] / 100)} ({"{:,.2f}".format(row["ko_rate"])}%)',
               tenor=row["tenor"],
               gtd=row["gtd"],
               locked=row["locked"],
            )
```

Add `bank_doc=row["bank_doc"],` after `locked=row["locked"],`:

```python
            ts = term_sheet(
               id=row["contract_ref"],
               bank_name=row["bank_name"],
               code=row["code"],
               strike_rate=row["strike_rate"],
               ko_rate=row["ko_rate"],
               stock_name=row["stock_name"] + f" ({row['code']})",
               shares= f'{"{:,.0f}".format(row["daily_shares"])} / {"{:,.0f}".format(row["daily_shares"] * 2)}' if row["leveraged"] == "Yes" else "{:,.0f}".format(row["daily_shares"]),
               spot="{:,.4f}".format(row["spot"]),
               strike=f'{"{:,.4f}".format(row["spot"]*row["strike_rate"]/100)} ({"{:,.2f}".format(row["strike_rate"])}%)',
               ko=f'{"{:,.4f}".format(row["spot"] * row["ko_rate"] / 100)} ({"{:,.2f}".format(row["ko_rate"])}%)',
               tenor=row["tenor"],
               gtd=row["gtd"],
               locked=row["locked"],
               bank_doc=row["bank_doc"],
            )
```

Finally, add the field to the `term_sheet` dataclass (lines 248-262):

```python
@dataclass
class term_sheet:
    id: int
    code: str
    bank_name: str
    stock_name: str
    shares: str
    spot: str
    strike_rate: str
    strike: str
    ko_rate: str
    ko: str
    tenor: str
    gtd: str
    locked: int = 0
```

Add `bank_doc: str = ""` after `locked: int = 0`:

```python
@dataclass
class term_sheet:
    id: int
    code: str
    bank_name: str
    stock_name: str
    shares: str
    spot: str
    strike_rate: str
    strike: str
    ko_rate: str
    ko: str
    tenor: str
    gtd: str
    locked: int = 0
    bank_doc: str = ""
```

- [ ] **Step 6: Add the indicator to the Trades Done list template**

The Trades Done table (`ltv_app/blueprints/transactions/pages/transactions/home.html`) does not currently render `bank_doc`/reference at all in its columns (`Account`, `Stock`, `Shares`, `Spot`, `Strike`, `KO`, `Tenor`, `GTD`, `Action` — see the `<thead>` at lines 67-71 and 122-125). Add a `Bank Ref` column: in the Accumulators `<thead>` (lines 67-71), change:

```html
            <tr>
                <th>Account</th><th>Stock</th><th class="text-right">Shares</th><th class="text-right">Spot</th>
                <th class="text-right">Strike</th><th class="text-right">KO</th>
                <th>Tenor</th><th>GTD</th><th class="text-center">Action</th>
            </tr>
```

to:

```html
            <tr>
                <th>Account</th><th>Stock</th><th class="text-right">Shares</th><th class="text-right">Spot</th>
                <th class="text-right">Strike</th><th class="text-right">KO</th>
                <th>Tenor</th><th>GTD</th><th>Bank Ref</th><th class="text-center">Action</th>
            </tr>
```

and in the matching row loop (lines 75-83), insert before the Action `<td>` (currently line 84):

```html
            <td>{% if ts.bank_doc %}{{ ts.bank_doc }}{% else %}<span class="text-danger">missing</span>{% endif %}</td>
```

Repeat both changes for the Decumulators `<thead>` (lines 122-125) and row loop (lines 130-138, insert before line 139).

- [ ] **Step 7: Verify all four surfaces live**

Reload the edit page from Step 1 → label should read "Bank Reference No. (missing)" in red. Reload the per-account Term Sheet list → that contract's reference cell should show a red "missing" badge. Reload Trades Done for a date containing that contract → new "Bank Ref" column should show the same red "missing" badge. Fill in a Bank Reference No. on the edit page, save, and reload all three surfaces again → indicator should be gone everywhere, replaced by the entered value.

- [ ] **Step 8: Commit**

```bash
git add ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html \
        ltv_app/blueprints/term_sheet/pages/term_sheet/add.html \
        ltv_app/blueprints/term_sheet/pages/term_sheet/home.html \
        ltv_app/blueprints/transactions/pages/transactions/home.html \
        ltv_app/blueprints/transactions/extensions/transaction_summary.py
git commit -m "fix(term-sheet): surface missing Bank Reference No. on form and list views"
```

---

### Task 4: Replace Print Trades Done popup with an in-page modal

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html:39-41` (button)
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html` (add a new modal block near the other `modal-overlay` blocks, e.g. after `contractModal`)
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html` (add a small script near `openTxnModal`/`closeTxnModal`, e.g. after line 808)

**Interfaces:**
- Consumes: existing `openTxnModal(id)` / `closeTxnModal(id)` JS helpers (lines 777-808 — toggle `.active` on `#<id>.modal-overlay`), existing route `transactions.print_with_gain_loss` (`ltv_app/blueprints/transactions/views.py:647-649`, path `/trades/print_with_gain_loss/<trade_date>`), existing `#trade_date` input (line 20) for the currently-selected date.
- Produces: new function `openPrintModal()` — not consumed elsewhere in this plan.

- [ ] **Step 1: Confirm current (unreliable) behavior live**

Navigate to `http://192.168.1.48:5001/trades/`. Click "Print Trades Done".

Expected (matches the reproduction session): no new window/tab appears, no visible effect — the existing `window.open(...)` call is silently blocked.

- [ ] **Step 2: Change the button**

In `ltv_app/blueprints/transactions/pages/transactions/home.html`, find:

```html
        <a href="{{ url_for('transactions.print_with_gain_loss', trade_date=trade_date) }}"
           onclick="window.open(this.href,'printTrades','width=1200,height=900,scrollbars=yes,resizable=yes'); return false;"
           class="btn btn-outline">Print Trades Done</a>
```

Replace with:

```html
        <button type="button" class="btn btn-outline" onclick="openPrintModal()">Print Trades Done</button>
```

- [ ] **Step 3: Add the modal block**

Immediately after the closing `</div>` of the existing `contractModal` block (search for `id="contractModal"`, insert after its matching closing `</div></div>`), add:

```html
<div class="modal-overlay" id="printModal">
<div class="modal" style="max-width:1100px;width:95vw;padding:0;">
    <div class="modal-header" style="margin:0;padding:16px 20px 12px;border-bottom:2px solid var(--accent);">
        <span class="modal-title">Trades Done — Print Preview</span>
        <button class="modal-close" onclick="closeTxnModal('printModal')">&times;</button>
    </div>
    <iframe id="print-modal-frame" src="about:blank"
            style="width:100%;height:80vh;border:none;display:block;"></iframe>
</div>
</div>
```

- [ ] **Step 4: Add the `openPrintModal()` function**

Immediately after the existing `closeTxnModal` function and its Escape-key/overlay-click listeners (search for `function closeTxnModal(id)`, insert after the block ending `m.addEventListener('click', function(e){ if(e.target===this) this.classList.remove('active'); });\n});`), add:

```javascript
function openPrintModal() {
    var tradeDate = document.getElementById('trade_date').value;
    document.getElementById('print-modal-frame').src =
        '/trades/print_with_gain_loss/' + tradeDate;
    openTxnModal('printModal');
}
```

- [ ] **Step 5: Verify the fix live**

Reload `http://192.168.1.48:5001/trades/`, click "Print Trades Done".

Expected: a modal opens in-page showing the Trades Done print report (Portrait/Landscape toggle, Decu table, Buy section, Transfer section) for the currently selected trade date, rendered inside the iframe. Close it (× button, Escape key, or clicking the overlay) → returns to the Trades Done page with the trade date filter unchanged.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/transactions/pages/transactions/home.html
git commit -m "fix(trades): show Print Trades Done in a modal instead of a blockable popup"
```

---

### Task 5: Live-update the per-row "To Decu" column

**Files:**
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html:246-255` (per-row cell)
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html:460-488` (`updateToDecuTotals()`)

**Interfaces:**
- Consumes: existing `.period-days` / `.period-received` input classes and `#daily_shares` / `#leveraged` fields (already wired to `updateToDecuTotals()`).
- Produces: new `.row-todecu` class on the per-row cell — not consumed elsewhere in this plan.

- [ ] **Step 1: Confirm current (stale) behavior live**

Navigate to an unlocked contract's edit page (e.g. `http://192.168.1.48:5001/term-sheet/edit/1455`, if still unlocked from the earlier reproduction session — otherwise any unlocked Decu/Accu contract). Change period 1's Days value.

Expected: the footer's Received/Remaining/Total figures update immediately (already correct), but that row's own "To Decu" column stays at its pre-edit value until the page is saved and reloaded.

- [ ] **Step 2: Convert the per-row cell to a live input**

In `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html`, find:

```html
                        <td style="padding: 0.18rem 0.5rem; text-align: right; color: var(--text-secondary);
                                   font-size: 0.8rem; font-family: monospace; white-space: nowrap;">
                            {% if sched.days %}
                                {% if ts.leveraged == "Yes" %}
                                    {{ "{:,}".format(sched.days * ts.daily_shares * 2) }}
                                {% else %}
                                    {{ "{:,}".format(sched.days * ts.daily_shares) }}
                                {% endif %}
                            {% endif %}
                        </td>
```

Replace with:

```html
                        <td style="padding: 0.18rem 0.3rem;">
                            <input readonly class="row-todecu" tabindex="-1"
                                   value="{% if sched.days %}{% if ts.leveraged == 'Yes' %}{{ "{:,}".format(sched.days * ts.daily_shares * 2) }}{% else %}{{ "{:,}".format(sched.days * ts.daily_shares) }}{% endif %}{% endif %}"
                                   style="width: 90px; text-align: right; font-size: 0.8rem; padding: 0.18rem 0.3rem;
                                          border: none; background: transparent; font-family: monospace;
                                          color: var(--text-secondary);">
                        </td>
```

- [ ] **Step 3: Extend `updateToDecuTotals()` to also write the row value**

Find:

```javascript
    var receivedTotal = 0, remainingTotal = 0;
    var daysInputs = document.querySelectorAll('.period-days');
    var recvInputs = document.querySelectorAll('.period-received');

    daysInputs.forEach(function(inp, i) {
        var days   = parseFloat(inp.value) || 0;
        var toDecu = days * multiplier;
        var hasReceived = recvInputs[i] && recvInputs[i].value.trim() !== '';
        if (hasReceived) receivedTotal  += toDecu;
        else             remainingTotal += toDecu;
    });

    function fmt(n) { return n ? Math.round(n).toLocaleString('en') : ''; }
```

Replace with:

```javascript
    var receivedTotal = 0, remainingTotal = 0;
    var daysInputs = document.querySelectorAll('.period-days');
    var recvInputs = document.querySelectorAll('.period-received');
    var rowInputs  = document.querySelectorAll('.row-todecu');

    function fmt(n) { return n ? Math.round(n).toLocaleString('en') : ''; }

    daysInputs.forEach(function(inp, i) {
        var days   = parseFloat(inp.value) || 0;
        var toDecu = days * multiplier;
        if (rowInputs[i]) rowInputs[i].value = fmt(toDecu);
        var hasReceived = recvInputs[i] && recvInputs[i].value.trim() !== '';
        if (hasReceived) receivedTotal  += toDecu;
        else             remainingTotal += toDecu;
    });
```

(`fmt` is moved above the loop so the loop body can call it; its later use for the footer totals below is unaffected since it's the same function, just declared earlier in the same scope.)

- [ ] **Step 4: Verify the fix live**

Reload the same contract edit page from Step 1. Change period 1's Days value.

Expected: that row's own "To Decu" cell updates immediately alongside the footer totals, using the same `days × daily_shares × (leveraged ? 2 : 1)` formula as before.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html
git commit -m "fix(term-sheet): live-update per-row To Decu column on period edit"
```

---

## Self-Review Notes

- **Spec coverage:** all 5 Group A items from the design spec have a task (Unlock 405 → Task 1, Fixings redirect → Task 2, Bank Reference indicator → Task 3, Print modal → Task 4, per-row To Decu → Task 5). Group B, Group C, and the bug #9 follow-up are explicitly out of scope per the spec and are not tasked here.
- **Placeholder scan:** no TBD/TODO. Task 3 originally had a "check before assuming" note for whether `bank_doc` was available on the Trades Done query — traced it during plan-writing (it wasn't: missing from `TransactionSummary.get_term_sheets()`'s SQL, its `term_sheet(...)` construction, and its dataclass) and replaced the note with the concrete three-part fix in Step 5.
- **Type/name consistency:** `.row-todecu` (Task 5) and `.period-days`/`.period-received` (existing) are consistent between Steps 2 and 3. `openPrintModal()` (Task 4) is defined and called with matching zero-arg signature. `fixings.home` / `trade_date` param names (Task 2) verified directly against `ltv_app/blueprints/fixings/views.py`, not assumed from the spec (the spec's first draft had this wrong — corrected before this plan was written).
