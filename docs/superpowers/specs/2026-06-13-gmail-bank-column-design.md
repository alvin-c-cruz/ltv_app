# Gmail Inbox — Bank Column Design

**Date:** 2026-06-13
**Status:** Approved

## Overview

Add a **BANK** column as the first column in the Gmail inbox table. It shows a short label identifying which bank/institution an email belongs to (e.g. SHK, DB, Trident). The label is auto-guessed from the sender's email domain. Any cell can be clicked to type an override, which persists to the database.

## Database

New table created with `CREATE TABLE IF NOT EXISTS` (no migration, no data loss risk):

```sql
CREATE TABLE IF NOT EXISTS tbl_gmail_thread_bank (
    thread_id TEXT PRIMARY KEY,
    bank_label TEXT NOT NULL
)
```

Created on first use inside `views.py`. Uses the existing `get_db()` connection.

## Backend

### `guess_bank(sender)` — `gmail_client.py`

Pure function, no DB access. Extracts the domain from the sender string (handles `"Name <email@domain.com>"` format) and looks it up in a hardcoded dict. Returns the bank label string, or `'—'` if no match.

**Domain mapping:**

| Domain | Label |
|---|---|
| `ebshk.com` | `SHK` |
| `db.com` | `DB` |
| `tridenttrust.com` | `Trident` |

Returns `'—'` for any unrecognised domain.

### `list_threads()` — `gmail_client.py`

Unchanged. Each thread summary dict already includes `sender`. The `bank` field is added at the view layer (not here), so the Gmail API module stays free of DB concerns.

### `inbox()` view — `views.py`

After calling `list_threads()`, the view:
1. Ensures `tbl_gmail_thread_bank` exists (`CREATE TABLE IF NOT EXISTS`)
2. Fetches all stored overrides for the returned thread IDs
3. For each thread: if a stored label exists, uses it; otherwise calls `guess_bank(thread['sender'])`
4. Adds `bank` key to each thread dict before passing to the template

### `PATCH /gmail/thread/<thread_id>/bank` — `views.py`

- Protected by `@login_required` + `@superuser_required`
- Requires `X-Requested-With: XMLHttpRequest` header (consistent with trash endpoint)
- Body: `{"bank_label": "SHK"}` (string, may be empty to clear override)
- If `bank_label` is empty string: deletes the row from `tbl_gmail_thread_bank` (resets to auto-guess)
- If non-empty: upserts into `tbl_gmail_thread_bank`
- Returns `200 {}` on success
- Returns `400 {"error": "..."}` if body is not valid JSON or `bank_label` key is missing
- Returns `503` if Gmail not configured (token missing — consistent with other endpoints)

## Frontend — `inbox.html`

### BANK column

Added as the first `<th>` and `<td>` in the inbox table. Width: `8%`. Displays `thread.bank`.

Responsive adjustments to the `@media (max-width: 1024px)` block:
- BANK column remains visible at all widths (compact label, no need to hide)
- Widths adjusted: BANK 8%, FROM 30%, SUBJECT 42%, DATE 20% (Snippet still hidden)

### Inline edit

- Clicking a `.bank-cell` replaces its text content with a small `<input>` (same width as cell, borderless style to feel inline)
- `input.value` initialised to the current label (empty string if `—`)
- On **Enter** or **blur**: if value unchanged, cancel; otherwise `PATCH` to save
- While saving: input disabled, slight opacity
- On **success**: update cell text, restore input to plain text
- On **error**: revert cell to previous value, briefly apply `color: var(--danger)` to signal failure
- Pressing **Escape**: cancel edit, revert to previous value

## Error Handling

| Scenario | Response | UI |
|---|---|---|
| Save success | 200 | Cell updates to new label |
| Network failure | — | Cell reverts, turns red briefly |
| 400 bad request | 400 | Cell reverts, turns red briefly |
| 503 not configured | 503 | Cell reverts, turns red briefly |

## Testing

New tests in `tests/functional/test_gmail.py`:

- `test_bank_patch_success` — PATCH with `{"bank_label": "SHK"}` returns 200
- `test_bank_patch_clear` — PATCH with `{"bank_label": ""}` returns 200
- `test_bank_patch_missing_key` — PATCH with `{}` returns 400
- `test_bank_patch_requires_superuser` — `auth_client` gets 403
- `test_bank_patch_requires_xhr` — PATCH without XHR header gets 403
- `test_bank_patch_unauthenticated` — unauthenticated gets 302

New unit tests in `tests/functional/test_gmail_client.py`:

- `test_guess_bank_ebshk` — `ebshk.com` → `SHK`
- `test_guess_bank_db` — `db.com` → `DB`
- `test_guess_bank_trident` — `tridenttrust.com` → `Trident`
- `test_guess_bank_unknown` — unknown domain → `—`
- `test_guess_bank_angle_bracket_format` — handles `"Name <email@ebshk.com>"` format

## Files Changed

| File | Change |
|---|---|
| `ltv_app/blueprints/gmail/extensions/gmail_client.py` | Add `BANK_DOMAINS` dict, `guess_bank()` function |
| `ltv_app/blueprints/gmail/views.py` | Enhance `inbox()` to merge bank labels; add `PATCH /gmail/thread/<id>/bank` |
| `ltv_app/blueprints/gmail/pages/gmail/inbox.html` | Add BANK column, inline edit JS, adjust responsive widths |
| `tests/functional/test_gmail.py` | Add 6 new route tests |
| `tests/functional/test_gmail_client.py` | Add 5 new unit tests |
