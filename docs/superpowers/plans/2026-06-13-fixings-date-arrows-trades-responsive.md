# Fixings Date Arrows + Trades Tablet Responsiveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add prev/next date arrow buttons to the Fixings toolbar, and hide the Action column in Trades Done tables at ≤1024px so data columns fit without overflow.

**Architecture:** Both changes are template-only — no Python, no backend, no database. Task 1 modifies `fixings/home.html` (add two buttons + `shiftDate()` JS). Task 2 modifies `transactions/home.html` (add a scoped `<style>` block). No automated tests exist for frontend-only template changes; verification is visual via the running dev server.

**Tech Stack:** Jinja2 templates, vanilla JS, CSS media queries.

---

### Task 1: Fixings — date arrow buttons

**Files:**
- Modify: `ltv_app/blueprints/fixings/pages/fixings/home.html:7-25`

Current toolbar form (lines 7–25):
```html
<div class="toolbar mt-3">
    <form method="post" action="{{ url_for('fixings.home') }}" class="toolbar-form">
        {{ date_form.csrf_token }}
        <div class="form-group">
            <label for="trade_date">Trade Date</label>
            <input type="date" name="trade_date" id="trade_date" value="{{ trade_date }}">
        </div>
        <div class="toolbar-actions">
            <button type="submit" class="btn btn-primary">Refresh</button>
        </div>
    </form>
    <div class="toolbar-actions" style="margin-left:auto;">
        ...
    </div>
</div>
```

- [ ] **Step 1: Add `id="fixings-date-form"` to the form, wrap the date input with arrow buttons, and append the `shiftDate()` script**

Replace lines 7–25 with:

```html
<div class="toolbar mt-3">
    <form method="post" action="{{ url_for('fixings.home') }}" class="toolbar-form" id="fixings-date-form">
        {{ date_form.csrf_token }}
        <div class="form-group">
            <label for="trade_date">Trade Date</label>
            <div style="display:flex;align-items:center;gap:4px">
                <button type="button" class="btn btn-outline" style="padding:0.25rem 0.6rem;font-size:1.1rem" onclick="shiftDate(-1)">&#8249;</button>
                <input type="date" name="trade_date" id="trade_date" value="{{ trade_date }}">
                <button type="button" class="btn btn-outline" style="padding:0.25rem 0.6rem;font-size:1.1rem" onclick="shiftDate(1)">&#8250;</button>
            </div>
        </div>
        <div class="toolbar-actions">
            <button type="submit" class="btn btn-primary">Refresh</button>
        </div>
    </form>
    <script>
    function shiftDate(days) {
        var p = document.getElementById('trade_date').value.split('-');
        var d = new Date(+p[0], +p[1] - 1, +p[2] + days);
        document.getElementById('trade_date').value =
            d.getFullYear() + '-' +
            String(d.getMonth() + 1).padStart(2, '0') + '-' +
            String(d.getDate()).padStart(2, '0');
        document.getElementById('fixings-date-form').submit();
    }
    </script>
    <div class="toolbar-actions" style="margin-left:auto;">
        <button type="button" class="btn btn-primary" onclick="openAddModal('{{ trade_date }}')">Add Fixing</button>
        <a href="{{ url_for('fixings.generate', trade_date=trade_date) }}" class="btn btn-success">Generate</a>
        {% if not has_fixings %}
        <a href="{{ url_for('fixings.record', trade_date=trade_date) }}" class="btn btn-outline"
           onclick="return confirm('Record fixings for {{ trade_date }}?')">Record Fixings</a>
        {% endif %}
    </div>
</div>
```

- [ ] **Step 2: Verify in browser**

Visit `http://192.168.68.100:5001/fixings/` (dev server must be running).

Confirm:
- `‹` and `›` buttons appear flanking the date input
- Clicking `‹` reloads the page with the previous calendar day
- Clicking `›` reloads the page with the next calendar day
- Crossing a month boundary works (e.g. navigate to June 1, click `‹` → shows May 31)
- The Refresh button still works (manual date + submit)
- CSRF token is included (form submits via POST, no 400 errors in server logs)

- [ ] **Step 3: Commit**

```bash
git add ltv_app/blueprints/fixings/pages/fixings/home.html
git commit -m "Add date arrow buttons to Fixings toolbar"
```

---

### Task 2: Trades Done — hide Action column at tablet width

**Files:**
- Modify: `ltv_app/blueprints/transactions/pages/transactions/home.html:1-6` (add style block after `{% block content %}`)

- [ ] **Step 1: Add a scoped `<style>` block at the top of `{% block content %}`**

Insert immediately after line 3 (`{% block content %}`), before line 5 (`<h1>Trades Done</h1>`):

```html
<style>
@media (max-width: 1024px) {
    .table-wrap th:last-child,
    .table-wrap td:last-child { display: none; }
}
</style>
```

The result should be:

```html
{% block content %}

<style>
@media (max-width: 1024px) {
    .table-wrap th:last-child,
    .table-wrap td:last-child { display: none; }
}
</style>

<h1>Trades Done</h1>
```

This hides the Action column (always the last `<th>`/`<td>`) in every `.table-wrap` table on this page:
- Accumulators (9 cols → 8 visible)
- Decumulators (9 cols → 8 visible)
- Regular transactions (8 cols → 7 visible)
- Short transactions (same as regular)

- [ ] **Step 2: Verify in browser at tablet width**

With the dev server running, resize the browser viewport to 900px wide (or use browser devtools device emulation at iPad size).

Visit `http://192.168.68.100:5001/trades/?trade_date=2026-06-12`

Confirm:
- Action column (Edit/Delete buttons) is hidden at ≤1024px
- All data columns — Account, Stock, Quantity, Price, Amount, Charges, Net Amount — are fully visible with no horizontal overflow
- No horizontal scrollbar appears
- Resize to >1024px: Action column reappears

- [ ] **Step 3: Commit**

```bash
git add ltv_app/blueprints/transactions/pages/transactions/home.html
git commit -m "Hide Action column in Trades Done tables at tablet width"
```
