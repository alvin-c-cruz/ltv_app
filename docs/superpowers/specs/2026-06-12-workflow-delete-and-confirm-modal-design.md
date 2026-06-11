# Workflow Delete Button & Confirm Modal Design

## Goal

Add a Delete button to the "1. Review Transactions" section of the workflow page, and replace all `confirm()` dialog calls on that page with a custom styled confirmation modal.

## Scope

Two files only:
- `ltv_app/blueprints/workflow/views.py` — new delete route
- `ltv_app/blueprints/workflow/pages/workflow/home.html` — modal, JS helpers, button changes

## Backend: New Delete Route

**Route:** `POST /workflow/delete/<source>/<ref_num>`  
**Location:** `workflow/views.py`

- `source` is one of `spot`, `short`, `contract`
- Deletes from the correct table:
  - `spot` → `DELETE FROM tbl_transaction WHERE ref_num=?`
  - `short` → `DELETE FROM tbl_transaction_short WHERE ref_num=?`
  - `contract` → `DELETE FROM tbl_stock_contract_period WHERE contract_ref=?` then `DELETE FROM tbl_stock_contract WHERE ref_num=?`
- Accepts `date_from` and `date_to` query params; redirects back to `workflow.home` with those params preserved (same pattern as `review_txn` and `lock_txn`)
- Requires `@login_required`; no extra role restriction (review-section records are always unlocked)

## Frontend: Shared Confirmation Modal

One `#confirmModal` added at the bottom of `home.html`. Uses existing app CSS classes (`modal-overlay`, `modal`, `btn btn-danger`, `btn btn-outline`).

```
┌─────────────────────────────┐
│  Confirm                    │
│                             │
│  <dynamic message>          │
│                             │
│  [Cancel]  [Confirm]        │
└─────────────────────────────┘
```

## Frontend: JS Helper

```javascript
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

Escape key closes the modal (added to existing `keydown` listener).

## confirm() Replacements (9 total)

All existing `onclick="return confirm(...)"` patterns replaced with `showConfirm(message, () => form.submit())`.

### Section 1 — Review Transactions

| Row type | Old | New |
|---|---|---|
| Spot (regular) | `onclick="return confirm('Mark this transaction as reviewed?')"` on Review button | `type="button"` + `showConfirm('Mark as reviewed?', () => form.submit())` |
| Fixing (ACCU/DECU) | `onclick="return confirm('Mark this fixing as reviewed?')"` | same pattern |
| Contract (term sheet) | `onclick="return confirm('Mark this term sheet as reviewed?')"` | same pattern |
| Bulk "Review Selected" | `if (!confirm(...))` inside `reviewSelected()` | `showConfirm(message, () => { build form; form.submit() })` |

### Section 3 — Lock Transactions

| Row type | Old | New |
|---|---|---|
| Spot (regular) | `onclick="return confirm('Lock this transaction?')"` | `showConfirm` pattern |
| Fixing (ACCU/DECU) | `onclick="return confirm('Lock this fixing?')"` | same |
| Contract (term sheet) | `onclick="return confirm('Lock this contract?')"` | same |
| Bulk "Lock Selected" | `if (!confirm(...))` inside `lockSelected()` | `showConfirm` pattern |

### New — Delete Button (Section 1 only)

A `Delete` button added to Action column for all 3 row types (spot/regular, fixing, contract). Each row has a hidden `<form method="post">` pointing to the new `workflow.delete_txn` route; the Delete button calls `showConfirm('Delete this transaction?', () => form.submit())`.

Message variants:
- Spot/Fixing: `'Delete this transaction?'`
- Contract: `'Delete this term sheet?'`

## Button Rendering Pattern

Before (form with confirm):
```html
<form method="post" action="..." style="display:inline">
    <button type="submit" class="btn btn-primary btn-sm"
            onclick="return confirm('...')">Review</button>
</form>
```

After (button captures form ref, shows modal):
```html
<form id="review-form-{{ row.ref_num }}" method="post" action="..."></form>
<button type="button" class="btn btn-primary btn-sm"
        onclick="showConfirm('Mark as reviewed?',
                 () => document.getElementById('review-form-{{ row.ref_num }}').submit())">
    Review
</button>
```

Forms are moved outside the inline flow (empty `<form>` tags) and buttons trigger them via JS.

## Out of Scope

- Replacing `confirm()` in other pages (term_sheet/edit.html, etc.) — separate task
- Bulk-delete in Review section — not requested
- Role restrictions on delete — none added (review section is always unlocked records)
