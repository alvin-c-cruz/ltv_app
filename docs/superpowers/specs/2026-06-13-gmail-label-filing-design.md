# Gmail Inbox — Label Filing Design

**Date:** 2026-06-13
**Status:** Approved

## Overview

Upgrade the Gmail inbox Bank column from free-text to a Gmail-label-backed dropdown. Add a Sub-label column (dependent on Bank). Add a File button that applies the sub-label and archives the thread in Gmail when both are set.

## Data Layer

### Gmail Label Hierarchy

`list_labels()` in `gmail_client.py` fetches all Gmail labels via the API and returns only those whose name starts with `"Alvin - "`. It builds a parent/child hierarchy using the `/` separator in label names:

- Parent: `"Alvin - SHK"` → short name `"SHK"`
- Child: `"Alvin - SHK/Statements"` → short name `"Statements"` (parent: `"Alvin - SHK"`)

Return structure:
```python
[
    {
        "id": "Label_123",
        "name": "Alvin - SHK",
        "short": "SHK",
        "children": [
            {"id": "Label_456", "name": "Alvin - SHK/Statements", "short": "Statements"},
            {"id": "Label_789", "name": "Alvin - SHK/Trades", "short": "Trades"},
        ]
    },
    ...
]
```

### Database

New table (replaces `tbl_gmail_thread_bank`, which launched with this sprint and has no historical value):

```sql
CREATE TABLE IF NOT EXISTS tbl_gmail_thread_labels (
    thread_id   TEXT PRIMARY KEY,
    bank_id     TEXT,        -- Gmail label ID for parent label
    sublabel_id TEXT         -- Gmail label ID for child label
)
```

`tbl_gmail_thread_bank` is left in place but no longer written to or read from.

## Backend

### `gmail_client.py` additions

**`list_labels()`**
- Calls `service.users().labels().list(userId='me')`
- Filters to labels whose `name` starts with `"Alvin - "`
- Builds parent/child hierarchy (child names contain `/` after the prefix)
- Returns list of parent dicts as described above
- Raises `FileNotFoundError`/`ValueError` on missing/invalid token (same as other functions)

**`apply_label_and_archive(thread_id, label_id)`**
- Calls `service.users().threads().modify()` with `addLabelIds=[label_id]`, `removeLabelIds=['INBOX']`
- Raises `HttpError` on API failure

### `views.py` changes

**`_ensure_labels_table(db)`** — helper, creates `tbl_gmail_thread_labels` if missing.

**`_get_stored_labels(db, thread_ids)`** — bulk-fetches `(thread_id, bank_id, sublabel_id)` rows, returns dict keyed by thread_id.

**`inbox()` updated** — calls `list_labels()` to get hierarchy, embeds it as `labels_json` in the template. Reads stored `bank_id`/`sublabel_id` from `tbl_gmail_thread_labels` and adds to each thread dict.

**`GET /gmail/labels`** — returns `list_labels()` as JSON for any future AJAX refresh. Protected by `@login_required` + `@superuser_required`. Returns 503 if not configured.

**`PATCH /gmail/thread/<id>/bank`** — updated:
- Accepts `{"bank_id": "Label_123"}` (Gmail label ID, not short text)
- If `bank_id` is empty string: clears both `bank_id` and `sublabel_id` in DB
- If non-empty: upserts `bank_id`, clears `sublabel_id` (bank change invalidates sub-label)
- Returns `200 {}` on success, `400` if key missing, `403` if no XHR header

**`PATCH /gmail/thread/<id>/sublabel`** — new:
- Requires `X-Requested-With: XMLHttpRequest`
- Accepts `{"sublabel_id": "Label_456"}`
- If empty: clears `sublabel_id` only
- If non-empty: upserts `sublabel_id`
- Returns `200 {}` on success, `400` if key missing

**`POST /gmail/thread/<id>/file`** — new:
- Requires `X-Requested-With: XMLHttpRequest`
- Reads `sublabel_id` from `tbl_gmail_thread_labels`
- If no `sublabel_id` stored: returns `400 {"error": "No sub-label set"}`
- Calls `apply_label_and_archive(thread_id, sublabel_id)`
- Returns `200 {}` on success
- Returns `404` if thread not found, `503` if not configured, `500` on other API errors

## Frontend — `inbox.html`

### Label hierarchy

Embedded in the page as an inline JS variable (populated server-side):
```html
<script>var LABELS = {{ labels_json|tojson }};</script>
```

`LABELS` is the same structure as `list_labels()` output. Dropdowns are built from this — no extra fetch needed.

### Table columns

**Desktop:**

| Column | Width |
|--------|-------|
| Bank | 8% |
| Sub-label | 10% |
| From | 22% |
| Subject | 26% |
| Date | 10% |
| File | 4% |
| Snippet | 20% |

**Tablet (≤1024px):** Bank 8%, Sub-label 12%, From 28%, Subject 36%, Date 16%. Snippet and File columns hidden (last-child + nth-child(6)).

### Bank cell

- Displays short name (e.g. "SHK") or "—" if unset
- Click → replaces content with a `<select>` pre-populated from `LABELS` parents
  - First option: `<option value="">— select —</option>`
  - Then one option per parent: `value = label.id`, text = `label.short`
  - Pre-selects stored `bank_id` if available
- On change: PATCHes `/bank` with `{bank_id: selectedValue}`, closes select, updates cell text, clears Sub-label cell to "—"
- On Escape: cancels, reverts to previous value
- `e.stopPropagation()` to prevent row expand

### Sub-label cell

- Displays short name (e.g. "Statements") or "—" if unset
- Click with no Bank set: does nothing (no tooltip needed — Bank cell is visually adjacent)
- Click with Bank set → replaces content with a `<select>` pre-populated from `LABELS` children of the current bank
  - First option: `<option value="">— select —</option>`
  - Then one option per child: `value = child.id`, text = `child.short`
  - Pre-selects stored `sublabel_id` if available
- On change: PATCHes `/sublabel` with `{sublabel_id: selectedValue}`, closes select, updates cell text; if sublabel is now set, shows File button for this row
- On Escape: cancels, reverts
- `e.stopPropagation()`

### File button

- A small `→` button in the File column cell, rendered only when `sublabel_id` is set for a thread
- When `sublabel_id` is absent, cell is empty
- Click: POSTs `/file`, disables button + shows "…" text while in-flight
- On success: removes the entire inbox row and expand row from the DOM (thread archived)
- On error: re-enables button, briefly turns red

## Error Handling

| Scenario | Response | UI |
|---|---|---|
| `list_labels()` fails at inbox load | Catch error, pass empty `labels_json=[]` | Bank/Sub-label cells show "—", dropdowns are empty (non-interactive) |
| Bank PATCH fails | 500/503 | Cell reverts, red flash |
| Sub-label PATCH fails | 500/503 | Cell reverts, red flash |
| File POST — no sub-label | 400 | Button re-enables, red flash |
| File POST — API error | 500 | Button re-enables, red flash |
| File POST — thread already gone | 404 | Remove row (treat as success) |

## Testing

### New unit tests — `test_gmail_client.py`

- `test_list_labels_filters_alvin_prefix` — only "Alvin -" labels returned
- `test_list_labels_builds_hierarchy` — children nested under correct parent
- `test_list_labels_short_names` — prefix/path stripped correctly

### New/updated route tests — `test_gmail.py`

- `test_labels_route_returns_json` — GET /gmail/labels returns 200 + list
- `test_labels_route_requires_superuser`
- `test_bank_patch_accepts_label_id` — PATCH with `bank_id` returns 200
- `test_bank_patch_clears_sublabel` — after bank PATCH, sublabel_id is NULL in DB
- `test_sublabel_patch_success`
- `test_sublabel_patch_missing_key` — returns 400
- `test_sublabel_patch_requires_superuser`
- `test_sublabel_patch_requires_xhr`
- `test_file_success` — mocked `apply_label_and_archive`, returns 200
- `test_file_no_sublabel_returns_400`
- `test_file_requires_superuser`
- `test_file_requires_xhr`
- `test_file_thread_not_found_returns_404`

## Files Changed

| File | Change |
|---|---|
| `ltv_app/blueprints/gmail/extensions/gmail_client.py` | Add `list_labels()`, `apply_label_and_archive()` |
| `ltv_app/blueprints/gmail/views.py` | Add `_ensure_labels_table()`, `_get_stored_labels()`; update `inbox()`, `update_bank()`; add `/labels`, `/sublabel`, `/file` routes |
| `ltv_app/blueprints/gmail/pages/gmail/inbox.html` | Embed `LABELS` JS var; replace Bank inline-edit with dropdown; add Sub-label column + dropdown; add File column + button; update widths/colspan |
| `tests/functional/test_gmail_client.py` | Add 3 `list_labels` unit tests |
| `tests/functional/test_gmail.py` | Add 13 new route tests; update existing bank tests to use `bank_id` |
