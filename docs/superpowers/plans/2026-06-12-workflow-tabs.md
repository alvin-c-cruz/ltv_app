# Workflow Page Tab Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the four stacked numbered sections on the workflow page with a card-tab UI (Option C) using labels: For Review / Charges / For Locking / Locked.

**Architecture:** Pure template change — all modifications are in `home.html`. A CSS `<style>` block defines the card tab component. Tab switching is client-side JS only (no URL param persistence; default tab is "For Review" on every page load). The four sections become hidden/visible `<div>` panels controlled by `switchWorkflowTab()`.

**Tech Stack:** Jinja2, HTML/CSS, vanilla JS. No Python changes. No test changes.

---

## File Map

| File | Change |
|------|--------|
| `ltv_app/blueprints/workflow/pages/workflow/home.html` | Only file modified — add CSS, replace 4 section wrappers + h2 headers with tab nav + tab panels, add tab switching JS |

---

### Task 1: Add card-tab CSS `<style>` block

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

Insert a `<style>` block immediately before the comment `<!-- SECTION 1: REVIEW -->` (currently line 51). Add it right after line 50 (the closing `</div>` of the date filter form block, just before the blank line before the SECTION 1 comment).

- [ ] **Step 1: Insert CSS block at line 51 (before the SECTION 1 comment)**

Insert this block between line 50 and line 51:

```html
<style>
/* ── Workflow card tabs ─────────────────────────────────── */
.workflow-tabs {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 0;
}
.workflow-tab {
    padding: 8px 18px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    color: var(--text-muted);
    background: #ede9df;
    user-select: none;
    transition: background 0.12s;
}
.workflow-tab.active {
    background: var(--surface);
    color: var(--text);
    font-weight: 600;
    border-color: #ccc;
}
.workflow-tab:hover:not(.active) {
    background: #e0ddd3;
}
.workflow-tab-body {
    background: var(--surface);
    border: 1px solid #ccc;
    border-radius: 0 6px 6px 6px;
    padding: 1.2rem 1.5rem 1.5rem;
    margin-bottom: 1.5rem;
}
.workflow-tab-panel { display: none; }
.workflow-tab-panel.active { display: block; }

/* ── Tab badge counts ───────────────────────────────────── */
.wf-badge {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 5px;
    vertical-align: middle;
}
.wf-badge-warn  { background: var(--accent);  color: white; }
.wf-badge-muted { background: #ccc;           color: #555;  }
.wf-badge-ok    { background: var(--success); color: white; }
</style>
```

- [ ] **Step 2: Verify the page still renders**

Load `http://192.168.100.79:5000/workflow/?date_from=2026-06-12&date_to=2026-06-12` and confirm no visual breakage — the sections should still appear as before (CSS doesn't alter existing elements yet).

---

### Task 2: Replace Section 1 wrapper + header with tab nav + first panel

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

Replace the comment `<!-- SECTION 1: REVIEW -->`, the `<div class="mt-4">` wrapper, and the inner header div (which contains the `<h2>` and `reviewSelectedBtn`) with: the tab nav HTML, an opening `<div class="workflow-tab-body">`, and an opening panel div. The `reviewSelectedBtn` is relocated inside the panel.

Lines being replaced:

```html
<!-- SECTION 1: REVIEW -->
<div class="mt-4">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h2 style="font-size:1.3rem; margin:0; color:var(--text-primary); border-bottom:2px solid var(--primary); padding-bottom:0.5rem; flex:1;">
            1. Review Transactions
            <span style="font-size:0.9rem; color:var(--text-muted); font-weight:normal;">
                ({{ review_total }} pending)
            </span>
        </h2>
        <button type="button" id="reviewSelectedBtn" class="btn btn-primary btn-sm" style="display:none; margin-left:1rem;"
                onclick="reviewSelected()">
            Review Selected (<span id="reviewSelectedCount">0</span>)
        </button>
    </div>
```

Replace with:

```html
<!-- ── Tab nav ─────────────────────────────────────────── -->
<div class="workflow-tabs mt-4">
    <div class="workflow-tab active" data-tab="review" onclick="switchWorkflowTab('review')">
        For Review
        <span class="wf-badge {% if review_total > 0 %}wf-badge-warn{% else %}wf-badge-muted{% endif %}">{{ review_total }}</span>
    </div>
    <div class="workflow-tab" data-tab="charges" onclick="switchWorkflowTab('charges')">
        Charges
        <span class="wf-badge {% if charges_total > 0 %}wf-badge-warn{% else %}wf-badge-muted{% endif %}">{{ charges_total }}</span>
    </div>
    <div class="workflow-tab" data-tab="locking" onclick="switchWorkflowTab('locking')">
        For Locking
        <span class="wf-badge {% if lock_total > 0 %}wf-badge-warn{% else %}wf-badge-muted{% endif %}">{{ lock_total }}</span>
    </div>
    <div class="workflow-tab" data-tab="locked" onclick="switchWorkflowTab('locked')">
        Locked
        <span class="wf-badge wf-badge-ok">{{ locked_total }}</span>
    </div>
</div>
<div class="workflow-tab-body">

<!-- TAB: For Review -->
<div id="tab-review" class="workflow-tab-panel active">
    <div style="display:flex; justify-content:flex-end; margin-bottom:0.8rem; min-height:2rem;">
        <button type="button" id="reviewSelectedBtn" class="btn btn-primary btn-sm" style="display:none;"
                onclick="reviewSelected()">
            Review Selected (<span id="reviewSelectedCount">0</span>)
        </button>
    </div>
```

- [ ] **Step 3: Also close the Section 1 panel div**

Find the closing `</div>` that currently ends the Section 1 outer wrapper (line 219). Replace it with:

```html
</div>
<!-- /TAB: For Review -->
```

- [ ] **Step 4: Load page and check Review tab renders correctly**

`http://192.168.100.79:5000/workflow/?date_from=2026-06-12&date_to=2026-06-12`

The card tab nav should appear. "For Review" tab should be active (white background). Tab body card should be visible with the transactions table. The other 3 tabs will still have their old section content below (we fix that next).

---

### Task 3: Convert Section 2 (Charges) to a tab panel

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

Lines being replaced (the Section 2 opening wrapper + h2):

```html
<!-- SECTION 2: CHARGES -->
<div class="mt-4">
    <h2 style="font-size:1.3rem; margin-bottom:1rem; color:var(--text-primary); border-bottom:2px solid var(--accent); padding-bottom:0.5rem;">
        2. Encode Charges
        <span style="font-size:0.9rem; color:var(--text-muted); font-weight:normal;">
            ({{ charges_total }} pending)
        </span>
    </h2>
```

Replace with:

```html
<!-- TAB: Charges -->
<div id="tab-charges" class="workflow-tab-panel">
```

Then find the closing `</div>` that ends Section 2 (currently at line 331). Replace it with:

```html
</div>
<!-- /TAB: Charges -->
```

- [ ] **Step 5: Click Charges tab and verify it shows correctly**

Load the page, click "Charges" tab → it should become active, the charges table should appear, and "For Review" content should hide.

---

### Task 4: Convert Section 3 (For Locking) to a tab panel

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

Lines being replaced (Section 3 opening wrapper + header div with h2 and lockSelectedBtn):

```html
<!-- SECTION 3: LOCK -->
<div class="mt-4">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <h2 style="font-size:1.3rem; margin:0; color:var(--text-primary); border-bottom:2px solid var(--danger); padding-bottom:0.5rem; flex:1;">
            3. Lock Transactions
            <span style="font-size:0.9rem; color:var(--text-muted); font-weight:normal;">
                ({{ lock_total }} pending)
            </span>
        </h2>
        <button type="button" id="lockSelectedBtn" class="btn btn-danger btn-sm" style="display:none; margin-left:1rem;"
                onclick="lockSelected()">
            Lock Selected (<span id="lockSelectedCount">0</span>)
        </button>
    </div>
```

Replace with:

```html
<!-- TAB: For Locking -->
<div id="tab-locking" class="workflow-tab-panel">
    <div style="display:flex; justify-content:flex-end; margin-bottom:0.8rem; min-height:2rem;">
        <button type="button" id="lockSelectedBtn" class="btn btn-danger btn-sm" style="display:none;"
                onclick="lockSelected()">
            Lock Selected (<span id="lockSelectedCount">0</span>)
        </button>
    </div>
```

Then find the closing `</div>` that ends Section 3 (currently at line 498). Replace it with:

```html
</div>
<!-- /TAB: For Locking -->
```

- [ ] **Step 6: Click For Locking tab and verify**

Load page, click "For Locking" → section shows (or shows empty state if no pending locks). Lock Selected button appears when checkboxes are ticked.

---

### Task 5: Convert Section 4 (Locked) to a tab panel, close tab body

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

Lines being replaced (Section 4 opening wrapper + h2):

```html
<!-- SECTION 4: LOCKED -->
<div class="mt-4 mb-4">
    <h2 style="font-size:1.3rem; margin-bottom:1rem; color:var(--text-primary); border-bottom:2px solid var(--success); padding-bottom:0.5rem;">
        4. Locked Transactions
        <span style="font-size:0.9rem; color:var(--text-muted); font-weight:normal;">
            ({{ locked_total }} locked)
        </span>
    </h2>
```

Replace with:

```html
<!-- TAB: Locked -->
<div id="tab-locked" class="workflow-tab-panel">
```

Then find the closing `</div>` that ends Section 4 (currently at line 614). Replace it with:

```html
</div>
<!-- /TAB: Locked -->

</div>
<!-- /workflow-tab-body -->
```

- [ ] **Step 7: Click Locked tab and verify**

Load page, click "Locked" → locked transactions table appears. Click back through all 4 tabs to confirm correct show/hide behaviour.

---

### Task 6: Add `switchWorkflowTab` JS function

**File:** `ltv_app/blueprints/workflow/pages/workflow/home.html`

The `<script>` block starts at line 616 (after the old section 4 closing div). Add the tab switching function at the very top of that script block, before the existing comment `// ── Shared confirmation modal`.

- [ ] **Step 8: Insert tab switching function at the start of the `<script>` block**

Find:

```html
<script>
// ── Shared confirmation modal ─────────────────────────────────────────
```

Replace with:

```html
<script>
// ── Workflow tab switching ────────────────────────────────────────────
function switchWorkflowTab(tabName) {
    document.querySelectorAll('.workflow-tab').forEach(function(t) {
        t.classList.toggle('active', t.dataset.tab === tabName);
    });
    document.querySelectorAll('.workflow-tab-panel').forEach(function(p) {
        p.classList.toggle('active', p.id === 'tab-' + tabName);
    });
}

// ── Shared confirmation modal ─────────────────────────────────────────
```

- [ ] **Step 9: Full end-to-end browser test**

Load `http://192.168.100.79:5000/workflow/?date_from=2026-06-12&date_to=2026-06-12`

Verify each of the following:

1. Tab nav shows 4 tabs: "For Review" (active/white), "Charges", "For Locking", "Locked"
2. Badge counts are correct and colour: gold if pending > 0, grey if 0, green for Locked
3. Clicking each tab switches the panel — previous panel hides, new one shows
4. In "For Review" tab: checkboxes → "Review Selected" button appears; Review/Delete buttons trigger custom confirm modal
5. In "For Locking" tab: checkboxes → "Lock Selected" button appears; Lock buttons trigger custom confirm modal
6. Date filter form still works — after filtering, page reloads to "For Review" tab (default)
7. No JS errors in browser console

- [ ] **Step 10: Commit**

```bash
git add ltv_app/blueprints/workflow/pages/workflow/home.html
git commit -m "Redesign workflow page: replace sections with card tabs (For Review / Charges / For Locking / Locked)"
```
