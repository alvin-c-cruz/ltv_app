# Gmail Inbox Admin Page — Design

**Date:** 2026-06-12
**Status:** Approved

## Overview

An admin-only page that displays larrylilia's Gmail inbox inside the LTV app. Superusers can view the 20 most recent threads and expand any thread inline to read the full conversation.

## Access Control

- Route: `/gmail/inbox` and `/gmail/thread/<thread_id>`
- Decorator: `@superuser_required` on both routes — defined in `ltv_app/blueprints/auth/views.py:superuser_required`, checks `current_user.role == 'superuser'`
- Non-superusers receive HTTP 403
- Navbar link ("Gmail Inbox") added to the superuser-only section of `ltv_app/templates/navbar.html` (alongside existing links at lines ~39-41)

## Blueprint Structure

```
ltv_app/blueprints/gmail/
├── __init__.py
├── views.py
├── extensions/
│   └── gmail_client.py
└── pages/
    └── gmail/
        └── inbox.html
```

## Routes

### `GET /gmail/inbox`

- Calls `gmail_client.list_threads(max_results=20)`
- Renders `inbox.html` with thread summaries: sender, subject, date, snippet
- On token missing: renders inbox.html with a "Gmail not configured" message and setup instructions
- On API error: flashes error detail, renders empty inbox

### `GET /gmail/thread/<thread_id>`

- AJAX endpoint — returns JSON only (no template)
- Calls `gmail_client.get_thread(thread_id)`
- Returns list of messages, each with: sender, date, plain-text body (HTML stripped)
- Thread not found (Gmail returns 404): returns `{"error": "Thread not found"}` with HTTP 404
- Other API error: returns `{"error": "<message>"}` with HTTP 500

## Gmail API Client (`extensions/gmail_client.py`)

Wraps `google-api-python-client`. Two public functions:

**`list_threads(max_results=20) -> list[dict]`**
- Calls `users.threads.list(userId='me', maxResults=max_results)`
- For each thread, calls `users.threads.get(format='metadata')` to extract sender, subject, date, snippet
- Returns list of dicts: `{id, sender, subject, date, snippet}`

**`get_thread(thread_id: str) -> list[dict]`**
- Calls `users.threads.get(userId='me', id=thread_id, format='full')`
- Extracts each message's sender, date, and body (prefers `text/plain`, falls back to stripping `text/html`)
- Returns list of dicts: `{sender, date, body}`

**Credential handling:**
- Reads `instance/gmail_token.json` on each call
- Auto-refreshes expired access token using stored refresh token
- Raises `FileNotFoundError` if token file missing (caller handles)
- Raises `ValueError` if token file exists but contains invalid JSON (caller treats as missing)
- Returns empty string for message body if neither `text/plain` nor `text/html` part exists

## Credential Setup (one-time)

A standalone script at `instance/gmail_setup.py`:
1. Reads `instance/gmail_client_secret.json` (downloaded from Google Cloud Console)
2. Runs OAuth2 consent flow in browser (opens `accounts.google.com`)
3. Saves resulting token to `instance/gmail_token.json`

Both files are gitignored.

**Required Google API scopes:** `https://www.googleapis.com/auth/gmail.readonly`

## UI — Inbox Page (`inbox.html`)

Extends the existing app base template. Superuser-only content.

**Thread list:**
- Table with columns: Sender, Subject, Date, Snippet
- Each row is clickable
- Clicking a row sends `GET /gmail/thread/<id>` (AJAX)
- Thread messages expand inline below the clicked row
- Clicking a second thread collapses the first
- Clicking the same row again collapses it

**Expanded thread:**
- Shows each message as a card: sender + date header, plain-text body
- Messages ordered oldest → newest

**Error state:**
- Token missing: shows alert with setup instructions ("Run instance/gmail_setup.py to configure Gmail access")
- API error: flash message at top of page, empty thread list

## Dependencies

Add to `requirements.txt`:
```
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
```

## Gitignore Additions

```
instance/gmail_token.json
instance/gmail_client_secret.json
```
