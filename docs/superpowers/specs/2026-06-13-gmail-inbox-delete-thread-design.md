# Gmail Inbox — Right-Click Actions (Trash & Open in Gmail)

**Date:** 2026-06-13
**Status:** Approved

## Overview

Add right-click context menu actions to the Gmail Inbox admin page (`/gmail/inbox`). Two actions: "Open in Gmail" (opens thread in a new tab) and "Move to Trash" (moves thread to Gmail Trash via API with confirmation). No full page reload required for either action.

## Scope Change

The existing OAuth token uses `gmail.readonly`. This feature requires `gmail.modify` to call the trash API. Both `gmail_client.py` and `gmail_setup.py` update their `SCOPES` constant. The existing token must be deleted and re-authorized via `gmail_setup.py`. **Already done as part of design.**

## Backend

### New route

```
POST /gmail/thread/<thread_id>/trash
```

- Protected by `@login_required` and `@superuser_required`
- Calls `trash_thread(thread_id)` in `gmail_client.py`
- Returns `200 {}` on success
- Returns `503 {'error': 'Gmail not configured'}` if token missing
- Returns `404 {'error': 'Thread not found'}` if Gmail API returns 404
- Returns `500 {'error': '...'}` on other API errors
- Only accepts POST — GET returns 405

### New client function

`trash_thread(thread_id)` in `ltv_app/blueprints/gmail/extensions/gmail_client.py`:

```python
def trash_thread(thread_id):
    service = _get_service()
    service.users().threads().trash(userId='me', id=thread_id).execute()
```

Raises `FileNotFoundError` / `ValueError` if not configured, `HttpError` on API failure.

## Frontend

All changes are in `ltv_app/blueprints/gmail/pages/gmail/inbox.html`. No new dependencies.

### Context menu

A hidden `<div id="ctx-menu">` absolutely positioned at the cursor on `contextmenu` event on any `.inbox-row`. Contains two items:

- **Open in Gmail** — opens `https://mail.google.com/mail/u/0/#inbox/<thread_id>` in a new tab
- **Move to Trash** — triggers confirmation modal

Dismissed by clicking anywhere else or pressing Escape. The currently targeted thread ID is stored in a JS variable when the menu opens.

### Confirmation modal

Uses existing fixings modal CSS classes. Shown when user clicks "Move to Trash" in the context menu. Contains:

- Message: "Move this thread to Trash?"
- **Cancel** button — closes modal, no action
- **Confirm** button — POSTs to `/gmail/thread/<id>/trash`

On success (`200`): modal closes, both the `inbox-row` and its `expand-<id>` row are removed from the DOM.

On error (non-200 or network failure): modal stays open, shows error message inside modal. Row is NOT removed.

## Error Handling

| Scenario | Response | UI behaviour |
|---|---|---|
| Success | 200 | Modal closes, row removed from DOM |
| Thread not found | 404 | Modal shows error, row stays |
| Not configured | 503 | Modal shows error, row stays |
| API error | 500 | Modal shows error, row stays |
| Network failure | — | Modal shows "Request failed", row stays |

## Testing

New tests added to `tests/functional/test_gmail.py`:

- `test_trash_thread_success` — POST returns 200
- `test_trash_thread_not_found` — mocked 404 HttpError returns 404
- `test_trash_thread_not_configured` — missing token returns 503
- `test_trash_thread_requires_superuser` — auth_client gets 403
- `test_trash_thread_get_not_allowed` — GET returns 405

## Files Changed

| File | Change |
|---|---|
| `ltv_app/blueprints/gmail/extensions/gmail_client.py` | Update SCOPES, add `trash_thread()` |
| `ltv_app/blueprints/gmail/views.py` | Add `POST /gmail/thread/<id>/trash` route |
| `ltv_app/blueprints/gmail/pages/gmail/inbox.html` | Add context menu, confirmation modal, JS handlers |
| `instance/gmail_setup.py` | Update SCOPES (already done) |
| `tests/functional/test_gmail.py` | Add 5 new tests |
