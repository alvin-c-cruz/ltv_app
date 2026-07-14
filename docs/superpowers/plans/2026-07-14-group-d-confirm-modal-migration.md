# Group D Confirm-Modal Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every remaining native `confirm()`/`prompt()` dialog in `ltv_app` (~26 call sites across 16 files, one shared Jinja macro) with the shared `showConfirmModal` component Group A introduced, extending that component's API only as far as real call sites require.

**Architecture:** No new subsystems. Task 1 extends `showConfirmModal(message, onConfirm, options)` with two additive, backward-compatible options (`variant`, `requireTyped`). Every later task swaps a native dialog for a call to this same function, following one of four established markup-conversion patterns (plain link, submit-button-tied-to-external-form, form `onsubmit`, raw JS `if (confirm(...))`) — no task invents a new pattern.

**Tech Stack:** Flask 3.1 (Jinja2 templates), vanilla JS (inline `<script>` blocks, no framework/bundler), existing `main.css`/`main.js`.

## Global Constraints

- No test suite exists in this copy of the repo (`tests/` removed, `pytest` unused) — every task's "test" step is a manual verification pass against the locally running app, driven via Chrome browser automation.
- `server/` is a git repo with a **public** GitHub remote (`alvin-c-cruz/ltv_app`). Never put real client data (account names, contract numbers, share counts, bank references) into code, comments, or commit messages.
- The local dev server binds to whatever LAN IP `socket.gethostbyname(socket.gethostname())` currently resolves to — **confirm the current URL before each task's verification** (it changed mid-session during Group A when the machine's network changed); don't assume a fixed IP across tasks.
- Login for verification: username `admin`, password `bugtest123` (set on a **local-only** DB copy — never the production credential).
- Every migrated call site must preserve its exact original confirmation message text and its exact original action (same route, same HTTP method, same resulting behavior) — only the dialog mechanism changes.
- `showConfirmModal`'s default variant (no `options` or `options.variant` omitted) is `'danger'` — this matches Group A's already-shipped Unlock call site exactly, so that site needs zero changes and no task may alter it.
- Deployment to PythonAnywhere is explicitly out of scope for this plan.

---

### Task 1: Extend the `showConfirmModal` component

**Files:**
- Modify: `ltv_app/static/js/main.js:52-68` (`showConfirmModal`/`closeConfirmModal`)
- Modify: `ltv_app/templates/base.html:14-26` (`#confirmModal` markup)

**Interfaces:**
- Consumes: nothing new — extends the existing `showConfirmModal(message, onConfirm)` Group A shipped.
- Produces: `showConfirmModal(message, onConfirm, options)` for every later task. `options` is optional and defaults to `{}`. `options.variant`: `'danger'` (default, red `btn-danger`) or `'primary'` (neutral `btn-primary`). `options.requireTyped`: omit for a plain modal, or an exact string (e.g. `'YES'`) to require typing that string into a new input before the Confirm button enables.

- [ ] **Step 1: Confirm current behavior live**

Find the current dev server URL (`ipconfig` or check the running process's startup log for `Starting host @ http://...`), log in as `admin`/`bugtest123`, navigate to `/trades/`, find a locked contract, click Unlock — confirm the existing modal (red Confirm button, no typed-input field) still works exactly as Group A left it. This is the baseline this task must not break.

- [ ] **Step 2: Replace `showConfirmModal`/`closeConfirmModal` in `main.js`**

Find (`ltv_app/static/js/main.js`, currently lines 52-68):

```js
function showConfirmModal(message, onConfirm) {
    var modal = document.getElementById('confirmModal');
    if (!modal) { if (onConfirm) onConfirm(); return; }
    document.getElementById('confirmModalMessage').textContent = message;
    var okBtn = document.getElementById('confirmModalOk');
    var newOkBtn = okBtn.cloneNode(true);
    okBtn.parentNode.replaceChild(newOkBtn, okBtn);
    newOkBtn.addEventListener('click', function () {
        closeConfirmModal();
        onConfirm();
    });
    modal.classList.add('active');
}
function closeConfirmModal() {
    var modal = document.getElementById('confirmModal');
    if (modal) modal.classList.remove('active');
}
```

Replace with:

```js
function showConfirmModal(message, onConfirm, options) {
    options = options || {};
    var modal = document.getElementById('confirmModal');
    if (!modal) { if (onConfirm) onConfirm(); return; }

    document.getElementById('confirmModalMessage').textContent = message;

    var okBtn = document.getElementById('confirmModalOk');
    var newOkBtn = okBtn.cloneNode(true);
    okBtn.parentNode.replaceChild(newOkBtn, okBtn);
    okBtn = newOkBtn;

    okBtn.className = 'btn ' + (options.variant === 'primary' ? 'btn-primary' : 'btn-danger');

    var typedInput = document.getElementById('confirmModalTypedInput');
    if (options.requireTyped) {
        typedInput.style.display = 'block';
        typedInput.value = '';
        okBtn.disabled = true;
        typedInput.oninput = function () {
            okBtn.disabled = typedInput.value !== options.requireTyped;
        };
    } else {
        typedInput.style.display = 'none';
        typedInput.oninput = null;
        okBtn.disabled = false;
    }

    okBtn.addEventListener('click', function () {
        closeConfirmModal();
        onConfirm();
    });
    modal.classList.add('active');
}
function closeConfirmModal() {
    var modal = document.getElementById('confirmModal');
    if (modal) modal.classList.remove('active');
    var typedInput = document.getElementById('confirmModalTypedInput');
    if (typedInput) { typedInput.value = ''; typedInput.style.display = 'none'; typedInput.oninput = null; }
}
```

- [ ] **Step 3: Add the typed-confirmation input to `base.html`**

Find (`ltv_app/templates/base.html`, currently lines 14-26):

```html
    <div class="modal-overlay" id="confirmModal">
    <div class="modal" style="max-width:420px;">
        <div class="modal-header">
            <span class="modal-title">Confirm</span>
            <button class="modal-close" onclick="closeConfirmModal()">&times;</button>
        </div>
        <p id="confirmModalMessage" style="margin:0 0 20px;"></p>
        <div style="display:flex;justify-content:flex-end;gap:10px;">
            <button type="button" class="btn btn-outline" onclick="closeConfirmModal()">Cancel</button>
            <button type="button" class="btn btn-danger" id="confirmModalOk">Confirm</button>
        </div>
    </div>
    </div>
```

Replace with (only the new `<input>` line is added, between the message `<p>` and the button row):

```html
    <div class="modal-overlay" id="confirmModal">
    <div class="modal" style="max-width:420px;">
        <div class="modal-header">
            <span class="modal-title">Confirm</span>
            <button class="modal-close" onclick="closeConfirmModal()">&times;</button>
        </div>
        <p id="confirmModalMessage" style="margin:0 0 20px;"></p>
        <input type="text" id="confirmModalTypedInput" style="display:none;width:100%;
               margin:0 0 16px;padding:8px 10px;box-sizing:border-box;" placeholder="Type to confirm" autocomplete="off">
        <div style="display:flex;justify-content:flex-end;gap:10px;">
            <button type="button" class="btn btn-outline" onclick="closeConfirmModal()">Cancel</button>
            <button type="button" class="btn btn-danger" id="confirmModalOk">Confirm</button>
        </div>
    </div>
    </div>
```

- [ ] **Step 4: Verify the baseline still works, then verify the new options**

Repeat Step 1's Unlock check — must still show a red Confirm button, no typed input, and still unlock the contract on Confirm. Then, from the browser console (`mcp__claude-in-chrome__javascript_tool` or the page's own console), manually exercise the two new paths to confirm they render correctly before any real call site uses them:
- `showConfirmModal('Test primary variant', function(){ console.log('confirmed'); }, {variant: 'primary'})` — Confirm button should render with `btn-primary` styling instead of red.
- `showConfirmModal('Test typed confirm', function(){ console.log('confirmed'); }, {requireTyped: 'YES'})` — a text input should appear, Confirm should be disabled until you type exactly `YES` into it, then Confirm should enable.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/static/js/main.js ltv_app/templates/base.html
git commit -m "feat(confirm-modal): add variant and requireTyped options"
```

---

### Task 2: Migrate `templates/macros.html`'s shared macros

**Files:**
- Modify: `ltv_app/templates/macros.html:94-106` (`btn_danger`, `btn_delete` macros)

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new — the macros' call signature (`btn_danger(text, url, confirm_message)`, `btn_delete(url, confirm_message, text)`) is unchanged, so `stocks/form.html` and `stocks/home.html` (the only callers) need no edits.

- [ ] **Step 1: Confirm current behavior live**

Navigate to the Stocks page (`/stocks/`), find a row using a delete-style button rendered by one of these macros, click it, confirm the native browser `confirm()` dialog appears (don't click through it if it would delete real data — Cancel it, or note the button's location for later re-verification).

- [ ] **Step 2: Migrate `btn_danger`**

Find (`ltv_app/templates/macros.html`, currently lines 94-98):

```html
{# Danger button with confirmation #}
{% macro btn_danger(text, url, confirm_message) %}
<a href="{{ url }}" class="btn btn-danger btn-sm"
   onclick="return confirm('{{ confirm_message }}')">{{ text }}</a>
{% endmacro %}
```

Replace with:

```html
{# Danger button with confirmation #}
{% macro btn_danger(text, url, confirm_message) %}
<button type="button" class="btn btn-danger btn-sm"
        onclick="showConfirmModal('{{ confirm_message }}', function(){ window.location.href = '{{ url }}'; })">{{ text }}</button>
{% endmacro %}
```

- [ ] **Step 3: Migrate `btn_delete`**

Find (currently lines 100-106):

```html
{# Delete button form (POST request) #}
{% macro btn_delete(url, confirm_message='Are you sure you want to delete this item?', text='Delete') %}
<form method="post" action="{{ url }}" style="display:inline">
    <button type="submit" class="btn btn-danger btn-sm"
            onclick="return confirm('{{ confirm_message }}')">{{ text }}</button>
</form>
{% endmacro %}
```

Replace with:

```html
{# Delete button form (POST request) #}
{% macro btn_delete(url, confirm_message='Are you sure you want to delete this item?', text='Delete') %}
{% set form_id = 'btn-delete-' ~ (url | replace('/', '-') | replace('?', '-') | replace('=', '-') | replace('&', '-')) %}
<form method="post" action="{{ url }}" style="display:inline" id="{{ form_id }}">
    <button type="button" class="btn btn-danger btn-sm"
            onclick="showConfirmModal('{{ confirm_message }}', function(){ document.getElementById('{{ form_id }}').submit(); })">{{ text }}</button>
</form>
{% endmacro %}
```

(the form id is derived deterministically from the delete `url` itself, with path/query separator characters replaced so it's a valid HTML id — since `url` already uniquely identifies the target of this specific delete action, two rendered instances of this macro on the same page can never collide, unlike a random suffix which has a small but real collision probability)

- [ ] **Step 4: Verify live**

Reload `/stocks/`, click a `btn_danger`-rendered button — confirm the new modal appears with the same message, red styling, and Cancel correctly aborts with no navigation. If the page also renders a `btn_delete` button, repeat for it (Cancel, don't complete a real delete unless you intend to and can undo it).

- [ ] **Step 5: Commit**

```bash
git add ltv_app/templates/macros.html
git commit -m "fix(macros): migrate btn_danger/btn_delete off native confirm()"
```

---

### Task 3: Migrate `fixings/home.html` and `fixings/transaction_macros.html`

**Files:**
- Modify: `ltv_app/blueprints/fixings/pages/fixings/home.html:36-38,96-98,118-119`
- Modify: `ltv_app/blueprints/fixings/pages/fixings/transaction_macros.html:31-32`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/fixings/`. Find a date with no fixings yet to see "Record Fixings"; find a locked and an unlocked fixing row to see "Unlock"/"Delete". Note native `confirm()` fires for each.

- [ ] **Step 2: Migrate "Record Fixings" (GET link)**

Find (`fixings/home.html`, currently lines 36-38):

```html
        <a href="{{ url_for('fixings.record', trade_date=trade_date) }}" class="btn btn-outline"
           onclick="return confirm('Record fixings for {{ trade_date }}?')">Record Fixings</a>
```

Replace with:

```html
        <button type="button" class="btn btn-outline"
                onclick="showConfirmModal('Record fixings for {{ trade_date }}?', function(){
                    window.location.href = '{{ url_for('fixings.record', trade_date=trade_date) }}';
                }, {variant: 'primary'})">Record Fixings</button>
```

- [ ] **Step 3: Migrate "Unlock" (GET link)**

Find (currently lines 96-98):

```html
                        <a href="{{ url_for('fixings.unlock', ref_num=t.id) }}" class="btn btn-outline btn-sm"
                           onclick="return confirm('Unlock this transaction?')">Unlock</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="showConfirmModal('Unlock this transaction?', function(){
                                    window.location.href = '{{ url_for('fixings.unlock', ref_num=t.id) }}';
                                })">Unlock</button>
```

- [ ] **Step 4: Migrate "Delete" (GET link)**

Find (currently lines 118-119):

```html
                        <a href="{{ url_for('fixings.delete', ref_num=t.id) }}" class="btn btn-danger btn-sm"
                           onclick="return confirm('Delete this fixing?')">Delete</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirmModal('Delete this fixing?', function(){
                                    window.location.href = '{{ url_for('fixings.delete', ref_num=t.id) }}';
                                })">Delete</button>
```

- [ ] **Step 5: Migrate `transaction_macros.html`'s "Delete"**

Find (`fixings/transaction_macros.html`, currently lines 31-32):

```html
                <a href="{{ url_for('fixings.delete', ref_num=transaction.id) }}" class="btn btn-danger btn-sm"
                   onclick="return confirm('Delete this fixing?')">Delete</a>
```

Replace with:

```html
                <button type="button" class="btn btn-danger btn-sm"
                        onclick="showConfirmModal('Delete this fixing?', function(){
                            window.location.href = '{{ url_for('fixings.delete', ref_num=transaction.id) }}';
                        })">Delete</button>
```

- [ ] **Step 6: Verify all four live**

Reload `/fixings/`. Confirm "Record Fixings" shows a neutral (`btn-primary`) modal (this action is routine, not destructive), and Confirm still navigates to the record route. Confirm "Unlock" shows the default red modal and still unlocks. Confirm "Delete" (both the `home.html` and `transaction_macros.html` instance, if both are reachable from the current data) shows the default red modal and still deletes. Confirm Cancel/Escape/backdrop-click all correctly abort with no navigation for each.

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/fixings/pages/fixings/home.html ltv_app/blueprints/fixings/pages/fixings/transaction_macros.html
git commit -m "fix(fixings): migrate Record/Unlock/Delete off native confirm()"
```

---

### Task 4: Migrate `charges/home.html` and `workflow/home.html`

**Files:**
- Modify: `ltv_app/blueprints/charges/pages/charges/home.html:79-87`
- Modify: `ltv_app/blueprints/workflow/pages/workflow/home.html:340-348,373-381`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/charges/` and `/workflow/`, find a "No Charges" button in each, confirm native `confirm()` fires.

- [ ] **Step 2: Migrate `charges/home.html`'s "No Charges" (form submit)**

Find (currently lines 79-87):

```html
                    <form method="post"
                          action="{{ url_for('charges.mark_no_charges', source=row.source, ref_num=row.ref_num) }}"
                          style="display:inline">
                        <button type="submit" class="btn btn-sm"
                                style="background:var(--accent-muted);color:var(--text-primary)"
                                onclick="return confirm('Mark this transaction as having no charges?')">
                            No Charges
                        </button>
                    </form>
```

Replace with:

```html
                    <form method="post" id="no-charges-form-{{ row.source }}-{{ row.ref_num }}"
                          action="{{ url_for('charges.mark_no_charges', source=row.source, ref_num=row.ref_num) }}"
                          style="display:inline">
                        <button type="button" class="btn btn-sm"
                                style="background:var(--accent-muted);color:var(--text-primary)"
                                onclick="showConfirmModal('Mark this transaction as having no charges?', function(){
                                    document.getElementById('no-charges-form-{{ row.source }}-{{ row.ref_num }}').submit();
                                }, {variant: 'primary'})">
                            No Charges
                        </button>
                    </form>
```

- [ ] **Step 3: Migrate `workflow/home.html`'s two "No Charges" instances (transaction rows and fixing rows)**

Find the first (currently lines 340-348, inside the transaction-rows loop):

```html
                        <form method="post"
                              action="{{ url_for('workflow.mark_no_charges', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-sm"
                                    style="background:var(--accent-muted);color:var(--text-primary)"
                                    onclick="return confirm('Mark this transaction as having no charges?')">
                                No Charges
                            </button>
                        </form>
```

Replace with:

```html
                        <form method="post" id="no-charges-form-{{ row.source }}-{{ row.ref_num }}"
                              action="{{ url_for('workflow.mark_no_charges', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="button" class="btn btn-sm"
                                    style="background:var(--accent-muted);color:var(--text-primary)"
                                    onclick="showConfirmModal('Mark this transaction as having no charges?', function(){
                                        document.getElementById('no-charges-form-{{ row.source }}-{{ row.ref_num }}').submit();
                                    }, {variant: 'primary'})">
                                No Charges
                            </button>
                        </form>
```

Find the second, near-identical instance (currently lines 373-381, inside the fixing-rows loop, message differs slightly — "fixing" not "transaction"):

```html
                        <form method="post"
                              action="{{ url_for('workflow.mark_no_charges', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-sm"
                                    style="background:var(--accent-muted);color:var(--text-primary)"
                                    onclick="return confirm('Mark this fixing as having no charges?')">
                                No Charges
                            </button>
                        </form>
```

Replace with:

```html
                        <form method="post" id="no-charges-fixing-form-{{ row.source }}-{{ row.ref_num }}"
                              action="{{ url_for('workflow.mark_no_charges', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="button" class="btn btn-sm"
                                    style="background:var(--accent-muted);color:var(--text-primary)"
                                    onclick="showConfirmModal('Mark this fixing as having no charges?', function(){
                                        document.getElementById('no-charges-fixing-form-{{ row.source }}-{{ row.ref_num }}').submit();
                                    }, {variant: 'primary'})">
                                No Charges
                            </button>
                        </form>
```

(the two `workflow/home.html` forms get differently-prefixed ids — `no-charges-form-` vs `no-charges-fixing-form-` — so a page rendering both a transaction row and a fixing row for the same `source`/`ref_num` pair, if that's ever possible, doesn't collide)

- [ ] **Step 4: Verify all three live**

Reload `/charges/` and `/workflow/`. Confirm each "No Charges" button shows a neutral (`btn-primary`) modal (routine workflow action) with the correct message, and Confirm still submits the form to the same `mark_no_charges` route (check the resulting page reflects the charge as marked). Confirm Cancel aborts with no submission.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/charges/pages/charges/home.html ltv_app/blueprints/workflow/pages/workflow/home.html
git commit -m "fix(charges,workflow): migrate No-Charges buttons off native confirm()"
```

---

### Task 5: Migrate `lock/home.html`

**Files:**
- Modify: `ltv_app/blueprints/lock/pages/lock/home.html:105-110,161-171`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/lock/`. Find a single-row "Lock" button and confirm native `confirm()` fires. Select multiple checkboxes, click the bulk "Lock Selected" button, confirm native `confirm()` fires there too.

- [ ] **Step 2: Migrate the single-row "Lock" (form submit)**

Find (currently lines 105-110):

```html
                    <form method="post"
                          action="{{ url_for('lock.lock_txn', source=row.source, ref_num=row.ref_num) }}"
                          style="display:inline">
                        <button type="submit" class="btn btn-danger btn-sm"
                                onclick="return confirm('Lock this transaction?')">Lock</button>
                    </form>
```

Replace with:

```html
                    <form method="post" id="lock-form-{{ row.source }}-{{ row.ref_num }}"
                          action="{{ url_for('lock.lock_txn', source=row.source, ref_num=row.ref_num) }}"
                          style="display:inline">
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirmModal('Lock this transaction?', function(){
                                    document.getElementById('lock-form-{{ row.source }}-{{ row.ref_num }}').submit();
                                }, {variant: 'primary'})">Lock</button>
                    </form>
```

(Lock is a routine, reversible-via-Unlock workflow step, not destructive — `variant: 'primary'`, matching the same categorization Group A already used to distinguish Lock from Unlock on the term-sheet edit page)

- [ ] **Step 3: Migrate the bulk "Lock Selected" (raw JS `if (confirm(...))`)**

Find (currently lines 161-195, the full `lockSelected()` function):

```js
function lockSelected() {
    const checkboxes = document.querySelectorAll('.txn-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('Please select at least one transaction to lock.');
        return;
    }

    const count = checkboxes.length;
    if (!confirm('Lock ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?')) {
        return;
    }

    // Build array of transactions to lock
    const transactions = [];
    checkboxes.forEach(function(cb) {
        transactions.push({
            source: cb.dataset.source,
            ref_num: cb.dataset.ref
        });
    });

    // Create form and submit
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '{{ url_for("lock.lock_multiple") }}';

    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'transactions';
    input.value = JSON.stringify(transactions);
    form.appendChild(input);

    document.body.appendChild(form);
    form.submit();
}
```

Replace with:

```js
function lockSelected() {
    const checkboxes = document.querySelectorAll('.txn-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('Please select at least one transaction to lock.');
        return;
    }

    const count = checkboxes.length;
    showConfirmModal('Lock ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?', function () {
        // Build array of transactions to lock
        const transactions = [];
        checkboxes.forEach(function(cb) {
            transactions.push({
                source: cb.dataset.source,
                ref_num: cb.dataset.ref
            });
        });

        // Create form and submit
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '{{ url_for("lock.lock_multiple") }}';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'transactions';
        input.value = JSON.stringify(transactions);
        form.appendChild(input);

        document.body.appendChild(form);
        form.submit();
    }, {variant: 'primary'});
}
```

(the `checkboxes` NodeList is captured before the modal opens and reused unchanged inside the callback — no re-querying needed, since the DOM doesn't change between "Lock Selected" being clicked and Confirm being clicked)

- [ ] **Step 4: Verify both live**

Reload `/lock/`. Confirm the single-row "Lock" button shows a neutral modal and still locks that one transaction. Select 2+ checkboxes, click "Lock Selected", confirm the modal shows the correct count in its message, and Confirm still locks all selected transactions (check they move out of the unlocked list). Confirm Cancel aborts both without submitting.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/lock/pages/lock/home.html
git commit -m "fix(lock): migrate single and bulk Lock off native confirm()"
```

---

### Task 6: Migrate `bank_accounts/home.html`

**Files:**
- Modify: `ltv_app/blueprints/bank_accounts/pages/bank_accounts/home.html:47-55`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/bank-accounts/` (or the app's actual route — check the nav or `url_for('bank_accounts.home')` usage if the path differs), find a Deactivate/Activate button, confirm native `confirm()` fires with the account name in the message.

- [ ] **Step 2: Migrate the Deactivate/Activate toggle (form submit)**

Find (currently lines 47-55):

```html
                <form method="post"
                      action="{{ url_for('bank_accounts.toggle_active', ref_num=acc.ref_num, show=show) }}"
                      style="display:inline">
                    <button type="submit" class="btn btn-sm"
                            style="background:var(--accent-muted); color:var(--text-primary)"
                            onclick="return confirm('{% if acc.is_active %}Deactivate{% else %}Activate{% endif %} {{ acc.bank_name }}?')">
                        {% if acc.is_active %}Deactivate{% else %}Activate{% endif %}
                    </button>
                </form>
```

Replace with:

```html
                <form method="post" id="toggle-active-form-{{ acc.ref_num }}"
                      action="{{ url_for('bank_accounts.toggle_active', ref_num=acc.ref_num, show=show) }}"
                      style="display:inline">
                    <button type="button" class="btn btn-sm"
                            style="background:var(--accent-muted); color:var(--text-primary)"
                            onclick="showConfirmModal('{% if acc.is_active %}Deactivate{% else %}Activate{% endif %} {{ acc.bank_name }}?', function(){
                                document.getElementById('toggle-active-form-{{ acc.ref_num }}').submit();
                            }, {variant: 'primary'})">
                        {% if acc.is_active %}Deactivate{% else %}Activate{% endif %}
                    </button>
                </form>
```

(a reversible toggle, not destructive — `variant: 'primary'`)

- [ ] **Step 3: Verify live**

Reload the bank accounts page. Click a Deactivate (or Activate) button, confirm the modal shows the correct verb and bank name, Confirm still toggles the account's active state (check the row's status reflects it), Cancel aborts with no change.

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/bank_accounts/pages/bank_accounts/home.html
git commit -m "fix(bank-accounts): migrate Deactivate/Activate off native confirm()"
```

---

### Task 7: Migrate `review/home.html`

**Files:**
- Modify: `ltv_app/blueprints/review/pages/review/home.html:36-41,110-115,169-174`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/review/`. If any of the three "Mark All ... Reviewed" buttons are visible (transactions, short transactions, contracts — each only renders when there's at least one unreviewed item of that kind), click one and confirm native `confirm()` fires via the form's `onsubmit`.

- [ ] **Step 2: Migrate "Mark All Transactions" (form `onsubmit`)**

Find (currently lines 36-41):

```html
        <form method="post" action="{{ url_for('review.mark_all') }}"
              onsubmit="return confirm('Mark all {{ total }} transaction(s) as reviewed?')">
            {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
            {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
            <button type="submit" class="btn btn-success">Mark All Transactions</button>
        </form>
```

Replace with:

```html
        <form method="post" action="{{ url_for('review.mark_all') }}" id="mark-all-form" onsubmit="return false">
            {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
            {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
            <button type="button" class="btn btn-success" onclick="showConfirmModal('Mark all {{ total }} transaction(s) as reviewed?', function(){
                document.getElementById('mark-all-form').submit();
            }, {variant: 'primary'})">Mark All Transactions</button>
        </form>
```

- [ ] **Step 3: Migrate "Mark All Short Reviewed" (form `onsubmit`)**

Find (currently lines 110-115):

```html
    <form method="post" action="{{ url_for('review.mark_all_short') }}"
          onsubmit="return confirm('Mark all {{ total_short }} short transaction(s) as reviewed?')">
        {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
        {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
        <button type="submit" class="btn btn-success btn-sm">Mark All Short Reviewed</button>
    </form>
```

Replace with:

```html
    <form method="post" action="{{ url_for('review.mark_all_short') }}" id="mark-all-short-form" onsubmit="return false">
        {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
        {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
        <button type="button" class="btn btn-success btn-sm" onclick="showConfirmModal('Mark all {{ total_short }} short transaction(s) as reviewed?', function(){
            document.getElementById('mark-all-short-form').submit();
        }, {variant: 'primary'})">Mark All Short Reviewed</button>
    </form>
```

- [ ] **Step 4: Migrate "Mark All Contracts Reviewed" (form `onsubmit`)**

Find (currently lines 169-174):

```html
    <form method="post" action="{{ url_for('review.mark_all_contracts') }}"
          onsubmit="return confirm('Mark all {{ total_contracts }} contract(s) as reviewed?')">
        {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
        {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
        <button type="submit" class="btn btn-success btn-sm">Mark All Contracts Reviewed</button>
    </form>
```

Replace with:

```html
    <form method="post" action="{{ url_for('review.mark_all_contracts') }}" id="mark-all-contracts-form" onsubmit="return false">
        {% if date_from %}<input type="hidden" name="date_from" value="{{ date_from }}">{% endif %}
        {% if date_to %}<input type="hidden" name="date_to" value="{{ date_to }}">{% endif %}
        <button type="button" class="btn btn-success btn-sm" onclick="showConfirmModal('Mark all {{ total_contracts }} contract(s) as reviewed?', function(){
            document.getElementById('mark-all-contracts-form').submit();
        }, {variant: 'primary'})">Mark All Contracts Reviewed</button>
    </form>
```

- [ ] **Step 5: Verify all three live**

For each of the three buttons that has at least one unreviewed item to test with, click it, confirm the modal shows the correct count and item-type in its message with neutral (`btn-primary`) styling, Confirm still submits the form (check the item(s) move to reviewed), Cancel aborts with no submission.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/review/pages/review/home.html
git commit -m "fix(review): migrate Mark-All-Reviewed forms off native confirm()"
```

---

### Task 8: Migrate `upload/inspect.html`

**Files:**
- Modify: `ltv_app/blueprints/upload/pages/upload/inspect.html:36-47`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to the upload inspect page (check `url_for('upload.inspect')` usage for the exact route). If files are present, confirm both the per-file "Delete" and the "Clear all" buttons trigger native `confirm()`.

- [ ] **Step 2: Migrate per-file "Delete" (form submit, dynamic message via `tojson`)**

Find (currently lines 36-39):

```html
                <form method="post" action="{{ url_for('upload.inspect_delete', filename=file.name) }}" style="margin:0">
                    <button type="submit" class="btn btn-outline btn-sm"
                            onclick="return confirm('Delete ' + {{ file.name|tojson }} + '?');">Delete</button>
                </form>
```

Replace with:

```html
                <form method="post" id="inspect-delete-form-{{ loop.index }}" action="{{ url_for('upload.inspect_delete', filename=file.name) }}" style="margin:0">
                    <button type="button" class="btn btn-outline btn-sm"
                            onclick="showConfirmModal('Delete ' + {{ file.name|tojson }} + '?', function(){
                                document.getElementById('inspect-delete-form-{{ loop.index }}').submit();
                            })">Delete</button>
                </form>
```

(`loop.index` gives each row's form a unique id within the `{% for file in files %}` loop this sits inside — confirmed present from the surrounding template structure)

- [ ] **Step 3: Migrate "Clear all" (`<input type="submit">` with `onclick`)**

Find (currently lines 45-48):

```html
    <form method="post" action="{{ url_for('upload.inspect_clear') }}" style="margin-top:1rem">
        <input type="submit" value="Clear all" class="btn btn-outline"
               onclick="return confirm('Delete all uploaded files?');">
    </form>
```

Replace with:

```html
    <form method="post" action="{{ url_for('upload.inspect_clear') }}" style="margin-top:1rem" id="inspect-clear-form">
        <input type="button" value="Clear all" class="btn btn-outline"
               onclick="showConfirmModal('Delete all uploaded files?', function(){
                   document.getElementById('inspect-clear-form').submit();
               })">
    </form>
```

(`<input type="button">`, not `type="submit"`, so clicking it no longer submits directly — same conversion principle as a `<button type="submit">`, just the `<input>` form of the element)

- [ ] **Step 4: Verify both live**

Reload the upload inspect page. Click a per-file "Delete" — confirm the modal message includes that exact filename, red styling, Confirm still deletes just that file, Cancel aborts. Click "Clear all" — confirm the modal appears, Confirm still clears all files, Cancel aborts.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/upload/pages/upload/inspect.html
git commit -m "fix(upload): migrate per-file and clear-all Delete off native confirm()"
```

---

### Task 9: Migrate `users/home.html`

**Files:**
- Modify: `ltv_app/blueprints/users/pages/users/home.html:40-42`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/users/`, find a Delete link, confirm native `confirm()` fires with the username in the message.

- [ ] **Step 2: Migrate "Delete" (GET link)**

Find (currently lines 40-42):

```html
                <a href="{{ url_for('users.delete', user_id=user.id) }}" class="btn btn-sm"
                   style="background:var(--accent-muted);color:var(--text-primary)"
                   onclick="return confirm('Delete {{ user.username }}? This cannot be undone.')">Delete</a>
```

Replace with:

```html
                <button type="button" class="btn btn-sm"
                        style="background:var(--accent-muted);color:var(--text-primary)"
                        onclick="showConfirmModal('Delete {{ user.username }}? This cannot be undone.', function(){
                            window.location.href = '{{ url_for('users.delete', user_id=user.id) }}';
                        })">Delete</button>
```

- [ ] **Step 3: Verify live**

Reload `/users/`. Click Delete on a non-critical test user if one exists (do not delete `admin` or any real account you need). Confirm the modal shows the correct username with red styling, Cancel aborts with no navigation. Only click Confirm if you have a disposable user to actually delete and can verify the row disappears.

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/users/pages/users/home.html
git commit -m "fix(users): migrate Delete off native confirm()"
```

---

### Task 10: Migrate `transactions/home.html`'s 8 remaining sites

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html:98-99,158-159,204-205,207-208,215-216,219-220,264-265,269-270`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new. (Group A's Unlock-contract sites at lines 89-92/144-147 already use `showConfirmModal` and are not touched by this task.)

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/trades/`. Find an unlocked contract (Delete), a locked spot/short transaction (Unlock), and an unlocked one (Delete) in each of the Buy/Sell and Short-book sections. Confirm native `confirm()` fires for each of the 8 sites below (some may require picking different trade dates to find a row of each kind).

- [ ] **Step 2: Migrate "Delete this contract?" (Accumulators table)**

Find (currently lines 98-99):

```html
                    <a href="{{ url_for('term_sheet.delete_contract', contract_ref=ts.id) }}" class="btn btn-danger btn-sm"
                       onclick="return confirm('Delete this contract?')">Delete</a>
```

Replace with:

```html
                    <button type="button" class="btn btn-danger btn-sm"
                            onclick="showConfirmModal('Delete this contract?', function(){
                                window.location.href = '{{ url_for('term_sheet.delete_contract', contract_ref=ts.id) }}';
                            })">Delete</button>
```

- [ ] **Step 3: Migrate "Delete this contract?" (Decumulators table)**

Find (currently lines 158-159 — identical markup to Step 2, different table):

```html
                    <a href="{{ url_for('term_sheet.delete_contract', contract_ref=ts.id) }}" class="btn btn-danger btn-sm"
                       onclick="return confirm('Delete this contract?')">Delete</a>
```

Replace with the same pattern as Step 2:

```html
                    <button type="button" class="btn btn-danger btn-sm"
                            onclick="showConfirmModal('Delete this contract?', function(){
                                window.location.href = '{{ url_for('term_sheet.delete_contract', contract_ref=ts.id) }}';
                            })">Delete</button>
```

- [ ] **Step 4: Migrate "Unlock this transaction?" (short-book branch, spot/short transactions loop)**

Find (currently lines 204-205):

```html
                        <a href="{{ url_for('transactions.unlock_short', ref_num=row['ref_num']) }}" class="btn btn-outline btn-sm"
                           onclick="return confirm('Unlock this transaction?')">Unlock</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="showConfirmModal('Unlock this transaction?', function(){
                                    window.location.href = '{{ url_for('transactions.unlock_short', ref_num=row['ref_num']) }}';
                                })">Unlock</button>
```

- [ ] **Step 5: Migrate "Unlock this transaction?" (regular branch, same loop)**

Find (currently lines 207-208):

```html
                        <a href="{{ url_for('transactions.unlock', ref_num=row['ref_num']) }}" class="btn btn-outline btn-sm"
                           onclick="return confirm('Unlock this transaction?')">Unlock</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="showConfirmModal('Unlock this transaction?', function(){
                                    window.location.href = '{{ url_for('transactions.unlock', ref_num=row['ref_num']) }}';
                                })">Unlock</button>
```

- [ ] **Step 6: Migrate "Delete this transaction?" (short-book branch, same loop)**

Find (currently lines 215-216):

```html
                        <a href="{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}" class="btn btn-danger btn-sm"
                           onclick="return confirm('Delete this transaction?')">Delete</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirmModal('Delete this transaction?', function(){
                                    window.location.href = '{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}';
                                })">Delete</button>
```

- [ ] **Step 7: Migrate "Delete this transaction?" (regular branch, same loop)**

Find (currently lines 219-220):

```html
                        <a href="{{ url_for('transactions.delete', ref_num=row['ref_num']) }}" class="btn btn-danger btn-sm"
                           onclick="return confirm('Delete this transaction?')">Delete</a>
```

Replace with:

```html
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirmModal('Delete this transaction?', function(){
                                    window.location.href = '{{ url_for('transactions.delete', ref_num=row['ref_num']) }}';
                                })">Delete</button>
```

- [ ] **Step 8: Migrate "Delete this transaction?" (short_transactions section, locked branch)**

Find (currently lines 264-265, inside the separate `{% for ccy in short_transactions %}` loop's locked-row branch):

```html
                    <a href="{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}" class="btn btn-danger btn-sm"
                       onclick="return confirm('Delete this transaction?')">Delete</a>
```

Replace with:

```html
                    <button type="button" class="btn btn-danger btn-sm"
                            onclick="showConfirmModal('Delete this transaction?', function(){
                                window.location.href = '{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}';
                            })">Delete</button>
```

- [ ] **Step 9: Migrate "Delete this transaction?" (short_transactions section, unlocked branch)**

Find (currently lines 269-270, same loop's unlocked-row branch — identical markup to Step 8):

```html
                    <a href="{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}" class="btn btn-danger btn-sm"
                       onclick="return confirm('Delete this transaction?')">Delete</a>
```

Replace with the same pattern as Step 8:

```html
                    <button type="button" class="btn btn-danger btn-sm"
                            onclick="showConfirmModal('Delete this transaction?', function(){
                                window.location.href = '{{ url_for('transactions.delete_short', ref_num=row['ref_num']) }}';
                            })">Delete</button>
```

- [ ] **Step 10: Verify all 8 live**

For each of the 8 sites, find or create a row exercising it, click the button, confirm the modal shows the correct message and variant (red for Delete/Unlock — no `options` needed, matching the component's default), Confirm still performs the original action (check the row's state changes accordingly), Cancel aborts with no navigation. Group A's already-migrated Unlock-contract buttons (Accumulators/Decumulators tables) must still work unchanged — spot-check one.

- [ ] **Step 11: Commit**

```bash
git add ltv_app/blueprints/transactions/pages/transactions/home.html
git commit -m "fix(transactions): migrate remaining Delete/Unlock links off native confirm()"
```

---

### Task 11: Migrate `term_sheet/edit.html` and `term_sheet/home.html`

**Files:**
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html:24-29,263-267,344-350`
- Modify: `ltv_app/blueprints/term_sheet/pages/term_sheet/home.html:151-174`

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` from Task 1.
- Produces: nothing new.

- [ ] **Step 1: Confirm current behavior live**

Navigate to an unlocked contract's edit page (e.g. `/term-sheet/edit/<id>` for any unlocked contract) — confirm the top-bar "Lock" button and a "Del" link on a period row both trigger native `confirm()`. Navigate to a locked contract's edit/view page — confirm the "Unlock" button (top bar) triggers native `confirm()`; scroll to the bottom action bar and confirm the second Unlock/Lock button pair there does too. Separately, on a per-account Term Sheet list page (`/term-sheet/<bank_id>`), right-click (or however the context menu triggers per `home.html`'s JS) a KO'd or DONE contract row to reach "Set Inactive"/"Set Active (undo KO)" and confirm native `confirm()` fires for those.

- [ ] **Step 2: Migrate the top-bar Unlock/Lock buttons in `edit.html`**

Find (currently lines 22-30):

```html
            {% if current_user.role == 'superuser' %}
            {% if locked %}
            <button type="submit" form="form-unlock" class="btn" style="background:#d97706;color:#fff;min-width:80px;"
                    onclick="return confirm('Unlock this contract?')">Unlock</button>
            {% else %}
            <button type="submit" form="form-lock" class="btn btn-secondary" style="min-width:80px;"
                    onclick="return confirm('Lock this contract?')">Lock</button>
            {% endif %}
            {% endif %}
```

Replace with:

```html
            {% if current_user.role == 'superuser' %}
            {% if locked %}
            <button type="button" class="btn" style="background:#d97706;color:#fff;min-width:80px;"
                    onclick="showConfirmModal('Unlock this contract?', function(){
                        document.getElementById('form-unlock').requestSubmit();
                    })">Unlock</button>
            {% else %}
            <button type="button" class="btn btn-secondary" style="min-width:80px;"
                    onclick="showConfirmModal('Lock this contract?', function(){
                        document.getElementById('form-lock').requestSubmit();
                    }, {variant: 'primary'})">Lock</button>
            {% endif %}
            {% endif %}
```

(these buttons use `form="form-unlock"`/`form="form-lock"` to submit a separate, standalone form defined later in the same template — `document.getElementById('form-unlock').requestSubmit()` submits that exact same form directly, so this is not a behavior change, just removing the HTML5 `form=` association in favor of doing it in JS)

- [ ] **Step 3: Migrate "Delete this period?" in the period-schedule table**

Find (currently lines 261-268):

```html
                        <td style="padding: 0.18rem 0.3rem; text-align: center;">
                            {% if not locked %}
                            <a href="{{ url_for('term_sheet.delete_period', contract_ref=contract_ref, period_ref=sched.ref_num) }}"
                               class="btn btn-danger"
                               style="font-size: 0.7rem; padding: 0.15rem 0.45rem;"
                               onclick="return confirm('Delete this period?')">Del</a>
                            {% endif %}
                        </td>
```

Replace with:

```html
                        <td style="padding: 0.18rem 0.3rem; text-align: center;">
                            {% if not locked %}
                            <button type="button"
                                    class="btn btn-danger"
                                    style="font-size: 0.7rem; padding: 0.15rem 0.45rem;"
                                    onclick="showConfirmModal('Delete this period?', function(){
                                        window.location.href = '{{ url_for('term_sheet.delete_period', contract_ref=contract_ref, period_ref=sched.ref_num) }}';
                                    })">Del</button>
                            {% endif %}
                        </td>
```

- [ ] **Step 4: Migrate the bottom-bar Unlock/Lock buttons in `edit.html`**

Find (currently lines 342-350 — same two messages/logic as Step 2, different location: bottom action bar):

```html
        {% if current_user.role == 'superuser' %}
        {% if locked %}
        <button type="submit" form="form-unlock" class="btn" style="background:#d97706;color:#fff;min-width:80px;"
                onclick="return confirm('Unlock this contract?')">Unlock</button>
        {% else %}
        <button type="submit" form="form-lock" class="btn btn-secondary" style="min-width:80px;"
                onclick="return confirm('Lock this contract?')">Lock</button>
        {% endif %}
        {% endif %}
```

Replace with the same pattern as Step 2 (this button pair submits the identical `form-unlock`/`form-lock` forms — there is only one of each form per page, referenced by both the top and bottom button):

```html
        {% if current_user.role == 'superuser' %}
        {% if locked %}
        <button type="button" class="btn" style="background:#d97706;color:#fff;min-width:80px;"
                onclick="showConfirmModal('Unlock this contract?', function(){
                    document.getElementById('form-unlock').requestSubmit();
                })">Unlock</button>
        {% else %}
        <button type="button" class="btn btn-secondary" style="min-width:80px;"
                onclick="showConfirmModal('Lock this contract?', function(){
                    document.getElementById('form-lock').requestSubmit();
                }, {variant: 'primary'})">Lock</button>
        {% endif %}
        {% endif %}
```

- [ ] **Step 5: Migrate "Set Inactive" in `home.html`'s context-menu JS**

Find (currently lines 151-174, the full `setInactiveOption` click handler):

```js
    setInactiveOption.addEventListener('click', function() {
        if (currentContractRef) {
            if (confirm('Are you sure you want to set this contract to inactive?')) {
                fetch(`{{ url_for('term_sheet.home', bank_id='') }}/../${currentContractRef}/set-inactive`, {
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

Replace with:

```js
    setInactiveOption.addEventListener('click', function() {
        if (currentContractRef) {
            showConfirmModal('Are you sure you want to set this contract to inactive?', function () {
                fetch(`{{ url_for('term_sheet.home', bank_id='') }}/../${currentContractRef}/set-inactive`, {
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
            }, {variant: 'primary'});
        }
        contextMenu.style.display = 'none';
    });
```

(Set Inactive is reversible via "Set Active (undo KO)" and involves no data loss — `variant: 'primary'`. Note `contextMenu.style.display = 'none'` now runs immediately regardless of what the user picks in the modal, same as it ran immediately before regardless of what the user picked in the native `confirm()` — behavior preserved exactly.)

- [ ] **Step 6: Migrate "Set Active (undo KO)" in `home.html`'s context-menu JS**

Find (currently lines 177-200, the full `setActiveOption` click handler):

```js
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

Replace with:

```js
    setActiveOption.addEventListener('click', function() {
        if (currentSetActiveUrl) {
            showConfirmModal('Undo the KO on this contract? It will become active again and will resume appearing in fixings, HKD margin, block/unblock and DECU positions.', function () {
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
            }, {variant: 'primary'});
        }
        contextMenu.style.display = 'none';
    });
```

("Set Active (undo KO)" is explicitly an undo action — `variant: 'primary'`)

- [ ] **Step 7: Verify all live**

Repeat Step 1's checks against the migrated code: top-bar and bottom-bar Unlock (red modal, still unlocks, both buttons submit the same underlying form so verifying one via each entry point is sufficient), Lock (neutral modal, still locks), Delete period (red modal, still deletes that one period row and the table renumbers/recalculates), Set Inactive (neutral modal, still sets inactive and reloads), Set Active/undo KO (neutral modal, still reactivates and reloads). Cancel/Escape/backdrop-click abort all of them with no request sent.

- [ ] **Step 8: Commit**

```bash
git add ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html ltv_app/blueprints/term_sheet/pages/term_sheet/home.html
git commit -m "fix(term-sheet): migrate Lock/Unlock/Delete-period/Set-Inactive/Undo-KO off native confirm()"
```

---

### Task 12: Migrate `dividends/home.html` and remove `confirmation_message()`

**Files:**
- Modify: `ltv_app/blueprints/dividends/pages/dividends/home.html:46`
- Modify: `ltv_app/static/js/main.js:46-49` (remove `confirmation_message()`)

**Interfaces:**
- Consumes: `showConfirmModal(message, onConfirm, options)` with `options.requireTyped` from Task 1.
- Produces: nothing new. This is the last task — after it, `confirmation_message()` and the `prompt()`-based flow no longer exist anywhere in the app.

- [ ] **Step 1: Confirm current behavior live**

Navigate to `/dividends/`, find a Delete button, click it, confirm the native `prompt("Type YES to proceed.", "")` dialog appears (Cancel/dismiss it — don't type YES unless you intend to delete real data).

- [ ] **Step 2: Migrate dividends "Delete"**

Find (`dividends/home.html`, currently line 46):

```html
        <a href="{{ url_for('dividends.delete', ref_num=dividend.ref_num) }}" class="btn btn-danger"  onclick="return confirmation_message()">Delete</a>
```

Replace with:

```html
        <button type="button" class="btn btn-danger" onclick="showConfirmModal('Delete this dividend?', function(){
            window.location.href = '{{ url_for('dividends.delete', ref_num=dividend.ref_num) }}';
        }, {requireTyped: 'YES'})">Delete</button>
```

- [ ] **Step 3: Remove `confirmation_message()` from `main.js`**

Find (`ltv_app/static/js/main.js`, currently lines 46-49):

```js
/* ── Confirmation dialog ──────────────────────────────────────── */
function confirmation_message() {
    return prompt("Type YES to proceed.", "") === 'YES';
}

```

Delete these 4 lines entirely (including the blank line after, so `main.js` flows directly from the "Clickable table rows" block into the "Shared confirm modal" block with the same single blank-line spacing the file uses elsewhere).

- [ ] **Step 4: Grep-confirm no other caller exists**

```bash
grep -rn "confirmation_message" ltv_app/
```

Expected: no output (the only two references — the definition and the one caller migrated in Step 2 — are both now gone).

- [ ] **Step 5: Verify live**

Reload `/dividends/`, click Delete. Confirm the new modal appears with a visible text input, Confirm button starts disabled, typing anything other than exactly `YES` keeps it disabled, typing `YES` enables it, Confirm then navigates to the delete route (only actually click through if you have a disposable test dividend row and can verify the deletion). Confirm Cancel/closing the modal resets the typed input (reopen it and check the input is empty again, not pre-filled from the last attempt).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/dividends/pages/dividends/home.html ltv_app/static/js/main.js
git commit -m "fix(dividends): migrate typed-confirm Delete off prompt(), remove confirmation_message()"
```

---

## Self-Review Notes

- **Spec coverage:** all 15 inventory rows from the spec have a task — component (Task 1), macros.html (Task 2), fixings ×2 files (Task 3), charges+workflow (Task 4), lock (Task 5), bank_accounts (Task 6), review (Task 7), upload (Task 8), users (Task 9), transactions' 8 remaining sites (Task 10), term_sheet's 7 sites across 2 files (Task 11), dividends + `confirmation_message()` removal (Task 12). All ~26 individual call sites are enumerated as individual steps, not summarized.
- **Placeholder scan:** no TBD/TODO; every step shows complete before/after code, not a description. No step says "similar to Task N" — even visually-identical sites (e.g. Task 10 Steps 2-3, Task 10 Steps 8-9) have their own full code blocks since an implementer may work out of order.
- **Variant assignments:** applied consistently per the spec's own categorization ("Delete/Unlock-class actions" → default `danger`, omit `options` entirely; "Lock/Mark-reviewed/Record-class actions" → `{variant: 'primary'}`) — Delete (all forms), Unlock (all forms) use the default; Lock, Record Fixings, No Charges, Deactivate/Activate, Mark-All-Reviewed (×3), bulk Lock, Set Inactive, Set Active/undo-KO all explicitly pass `{variant: 'primary'}`.
- **Type/name consistency:** every task's call sites use the exact `showConfirmModal(message, onConfirm, options)` signature Task 1 defines — no task invents a different parameter order or name. Every dynamically-generated form `id` (e.g. `no-charges-form-{{ row.source }}-{{ row.ref_num }}`, `lock-form-{{ row.source }}-{{ row.ref_num }}`, `toggle-active-form-{{ acc.ref_num }}`, `inspect-delete-form-{{ loop.index }}`, `btn-delete-<sanitized-url>`) is unique per rendered row within its loop, verified against each template's actual loop variable available at that point. Task 2's macro id was switched from a random suffix to a URL-derived one during self-review — the random version had a small but real cross-row collision probability on a page rendering the macro many times; the URL-derived version can't collide since each delete URL already uniquely identifies its target.
