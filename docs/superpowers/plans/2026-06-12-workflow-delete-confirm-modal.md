# Workflow Delete Button & Confirm Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Delete button to the Review Transactions section of the workflow page and replace all `confirm()` dialog calls on that page with a custom styled confirmation modal.

**Architecture:** A single shared `#confirmModal` sits at the bottom of `home.html`. A `showConfirm(message, callback)` JS helper stores a pending callback and shows the modal; Cancel clears it, Confirm fires it. All existing `confirm()` and `alert()` calls are replaced by `showConfirm` calls that submit the appropriate hidden form. A new `POST /workflow/delete/<source>/<ref_num>` route handles deletion for spot, short, and contract records, redirecting back to the workflow page with the date range preserved.

**Tech Stack:** Flask, Jinja2, vanilla JavaScript, SQLite via `get_db()`

---

### Task 1: Backend — delete_txn route

**Files:**
- Modify: `ltv_app/blueprints/workflow/views.py` (after the `lock_multiple` function, ~line 731)

- [ ] **Step 1: Add the route**

Open `ltv_app/blueprints/workflow/views.py`. After the `lock_multiple` function, add:

```python
@bp.route('/delete/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def delete_txn(source, ref_num):
    db = get_db()
    if source == 'contract':
        db.execute("DELETE FROM tbl_stock_contract_period WHERE contract_ref=?", (ref_num,))
        db.execute("DELETE FROM tbl_stock_contract WHERE ref_num=?", (ref_num,))
    elif source == 'short':
        db.execute("DELETE FROM tbl_transaction_short WHERE ref_num=?", (ref_num,))
    else:
        db.execute("DELETE FROM tbl_transaction WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction deleted.")
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))
```

- [ ] **Step 2: Verify the server starts cleanly**

```bash
cd C:/envs/LTV/server
python -c "from ltv_app import create_app; app = create_app(); print('OK')"
```

Expected output: `OK` (no import errors).

- [ ] **Step 3: Commit**

```bash
git add ltv_app/blueprints/workflow/views.py
git commit -m "Add workflow delete_txn route"
```

---

### Task 2: Confirm modal — HTML

**Files:**
- Modify: `ltv_app/blueprints/workflow/pages/workflow/home.html`

The modal goes just before the closing `{% endblock %}` tag (line 1491), after all the other modals.

- [ ] **Step 1: Add the confirm modal HTML**

Find this line near the bottom of `home.html`:
```html
{% endblock %}
```

Insert immediately before it:

```html
{# ── Shared Confirmation Modal ───────────────────────────────────────── #}
<div class="modal-overlay" id="confirmModal" onclick="if(event.target===this)confirmCancel()">
    <div class="modal" style="max-width:400px;">
        <div class="modal-header">
            <span class="modal-title">Confirm</span>
            <button type="button" class="modal-close" onclick="confirmCancel()">&times;</button>
        </div>
        <div style="padding:1.5rem;">
            <p id="confirmMessage" style="margin:0 0 1.5rem; font-size:1rem;"></p>
            <div class="form-actions">
                <button type="button" class="btn btn-danger" onclick="confirmOk()">Confirm</button>
                <button type="button" class="btn btn-outline" onclick="confirmCancel()">Cancel</button>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 2: Verify the page renders**

Visit `http://127.0.0.1:5000/workflow/` in a browser (or via curl returning 200). The modal is hidden by default so the page should look unchanged.

---

### Task 3: Confirm modal — JavaScript helpers

**Files:**
- Modify: `ltv_app/blueprints/workflow/pages/workflow/home.html` (inside the existing `<script>` block)

- [ ] **Step 1: Add the JS helpers**

In the `<script>` block (line 607), add these three functions at the very top (before `// Review section`):

```javascript
// ── Shared confirmation modal ─────────────────────────────────────────
let _confirmCallback = null;

function showConfirm(message, onConfirm) {
    document.getElementById('confirmMessage').textContent = message;
    _confirmCallback = onConfirm;
    document.getElementById('confirmModal').classList.add('active');
}

function confirmOk() {
    document.getElementById('confirmModal').classList.remove('active');
    if (_confirmCallback) { _confirmCallback(); _confirmCallback = null; }
}

function confirmCancel() {
    document.getElementById('confirmModal').classList.remove('active');
    _confirmCallback = null;
}
```

- [ ] **Step 2: Add confirmCancel to the Escape key listener**

Find the existing keydown listener (around line 896):
```javascript
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { closeEditModal(); closeFixingWfModal(); closeContractWfModal(); }
});
```

Replace it with:
```javascript
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { closeEditModal(); closeFixingWfModal(); closeContractWfModal(); confirmCancel(); }
});
```

- [ ] **Step 3: Manually verify the modal works**

Open the browser console on the workflow page and run:
```javascript
showConfirm('Test message?', () => console.log('confirmed'));
```
Expected: modal appears with "Test message?". Click Confirm → console logs "confirmed". Click Cancel or Escape → modal closes.

---

### Task 4: Section 1 — Replace Review confirm() calls and add Delete buttons

This is the biggest change. For each of the 3 row loops in Section 1 (spot_rows, fixing_rows, contract_rows), we:
1. Replace the inline `<form>` + submit button with an empty `<form>` + `type="button"` calling `showConfirm`
2. Add a Delete form + Delete button using the same pattern

**Files:**
- Modify: `ltv_app/blueprints/workflow/pages/workflow/home.html` (lines 107–196)

#### 4a: Spot rows (regular transactions)

- [ ] **Step 1: Replace the Review button in spot_rows**

Find this block (around line 123):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openEditModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-primary btn-sm"
                                    onclick="return confirm('Mark this transaction as reviewed?')">Review</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openEditModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form id="rev-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-primary btn-sm"
                                onclick="showConfirm('Mark as reviewed?', () => document.getElementById('rev-{{ row.ref_num }}').submit())">Review</button>
                        <form id="del-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.delete_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Delete this transaction?', () => document.getElementById('del-{{ row.ref_num }}').submit())">Delete</button>
                    </td>
```

#### 4b: Fixing rows (ACCU/DECU fixings)

- [ ] **Step 2: Replace the Review button in fixing_rows**

Find this block (around line 153):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openFixingWfModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-primary btn-sm"
                                    onclick="return confirm('Mark this fixing as reviewed?')">Review</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openFixingWfModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form id="rev-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-primary btn-sm"
                                onclick="showConfirm('Mark as reviewed?', () => document.getElementById('rev-{{ row.ref_num }}').submit())">Review</button>
                        <form id="del-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.delete_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Delete this transaction?', () => document.getElementById('del-{{ row.ref_num }}').submit())">Delete</button>
                    </td>
```

#### 4c: Contract rows (term sheets)

- [ ] **Step 3: Replace the Review button in contract_rows**

Find this block (around line 184):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openContractWfModal({{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-primary btn-sm"
                                    onclick="return confirm('Mark this term sheet as reviewed?')">Review</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openContractWfModal({{ row.ref_num }})">Edit</button>
                        <form id="rev-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.review_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-primary btn-sm"
                                onclick="showConfirm('Mark as reviewed?', () => document.getElementById('rev-{{ row.ref_num }}').submit())">Review</button>
                        <form id="del-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.delete_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Delete this term sheet?', () => document.getElementById('del-{{ row.ref_num }}').submit())">Delete</button>
                    </td>
```

#### 4d: Bulk "Review Selected"

- [ ] **Step 4: Replace confirm() in reviewSelected()**

Find the `reviewSelected` function (around line 642). Replace the entire function body with:

```javascript
function reviewSelected() {
    const checkboxes = document.querySelectorAll('.review-checkbox:checked');
    if (checkboxes.length === 0) return;
    const count = checkboxes.length;
    const transactions = [];
    checkboxes.forEach(function(cb) {
        transactions.push({ source: cb.dataset.source, ref_num: cb.dataset.ref });
    });
    showConfirm('Review ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?', function() {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '{{ url_for("workflow.review_multiple", date_from=date_from, date_to=date_to) }}';
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'transactions';
        input.value = JSON.stringify(transactions);
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    });
}
```

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/workflow/pages/workflow/home.html
git commit -m "Section 1: replace confirm() with modal, add Delete buttons"
```

---

### Task 5: Section 3 — Replace Lock confirm() calls

**Files:**
- Modify: `ltv_app/blueprints/workflow/pages/workflow/home.html` (lines 377–478)

#### 5a: Spot rows

- [ ] **Step 1: Replace the Lock button in spot_rows (Section 3)**

Find this block (around line 393):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openEditModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-danger btn-sm"
                                    onclick="return confirm('Lock this transaction?')">Lock</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openEditModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form id="lock-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Lock this transaction?', () => document.getElementById('lock-{{ row.ref_num }}').submit())">Lock</button>
                    </td>
```

#### 5b: Fixing rows (Section 3)

- [ ] **Step 2: Replace the Lock button in fixing_rows (Section 3)**

Find this block (around line 429):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openFixingWfModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-danger btn-sm"
                                    onclick="return confirm('Lock this fixing?')">Lock</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openFixingWfModal('{{ row.source }}', {{ row.ref_num }})">Edit</button>
                        <form id="lock-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Lock this fixing?', () => document.getElementById('lock-{{ row.ref_num }}').submit())">Lock</button>
                    </td>
```

#### 5c: Contract rows (Section 3)

- [ ] **Step 3: Replace the Lock button in contract_rows (Section 3)**

Find this block (around line 466):
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openContractWfModal({{ row.ref_num }})">Edit</button>
                        <form method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:inline">
                            <button type="submit" class="btn btn-danger btn-sm"
                                    onclick="return confirm('Lock this contract?')">Lock</button>
                        </form>
                    </td>
```

Replace with:
```html
                    <td class="text-center" style="white-space:nowrap">
                        <button type="button" class="btn btn-outline btn-sm"
                                onclick="openContractWfModal({{ row.ref_num }})">Edit</button>
                        <form id="lock-{{ row.ref_num }}" method="post"
                              action="{{ url_for('workflow.lock_txn', source=row.source, ref_num=row.ref_num, date_from=date_from, date_to=date_to) }}"
                              style="display:none"></form>
                        <button type="button" class="btn btn-danger btn-sm"
                                onclick="showConfirm('Lock this contract?', () => document.getElementById('lock-{{ row.ref_num }}').submit())">Lock</button>
                    </td>
```

#### 5d: Bulk "Lock Selected"

- [ ] **Step 4: Replace confirm() in lockSelected()**

Find the `lockSelected` function (around line 710). Replace the entire function body with:

```javascript
function lockSelected() {
    const checkboxes = document.querySelectorAll('.lock-checkbox:checked');
    if (checkboxes.length === 0) return;
    const count = checkboxes.length;
    const transactions = [];
    checkboxes.forEach(function(cb) {
        transactions.push({ source: cb.dataset.source, ref_num: cb.dataset.ref });
    });
    showConfirm('Lock ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?', function() {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '{{ url_for("workflow.lock_multiple", date_from=date_from, date_to=date_to) }}';
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'transactions';
        input.value = JSON.stringify(transactions);
        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
    });
}
```

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/workflow/pages/workflow/home.html
git commit -m "Section 3: replace confirm() with modal on Lock buttons"
```

---

### Task 6: Manual verification

- [ ] **Step 1: Start the server**

```bash
cd C:/envs/LTV/server
python flask_app.py
```

- [ ] **Step 2: Navigate to the workflow page with transactions present**

Open `http://192.168.100.79:5000/workflow/?date_from=2026-06-11&date_to=2026-06-12`

- [ ] **Step 3: Verify Review button shows custom modal**

Click any "Review" button in Section 1. Confirm the modal pops up with the message "Mark as reviewed?" and has Confirm / Cancel buttons. Click Cancel — nothing happens. Click Confirm — transaction is marked reviewed and page reloads.

- [ ] **Step 4: Verify Delete button shows custom modal**

Click any "Delete" button in Section 1. Confirm the modal shows "Delete this transaction?" (or "Delete this term sheet?" for contract rows). Click Cancel — nothing happens. Click Confirm — record is deleted and page reloads with the same date range.

- [ ] **Step 5: Verify Lock button shows custom modal**

Click any "Lock" button in Section 3. Confirm modal shows "Lock this transaction?" Click Confirm — transaction is locked and page reloads.

- [ ] **Step 6: Verify bulk actions use the modal**

Check 2–3 Review checkboxes → click "Review Selected" → modal shows "Review 3 selected transactions?" Click Confirm → all marked reviewed.

- [ ] **Step 7: Verify Escape key closes modal**

Open any modal (e.g. click a Delete button), then press Escape. Modal should close without taking action.

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "Workflow: delete button and custom confirm modal, remove all confirm() dialogs"
```
