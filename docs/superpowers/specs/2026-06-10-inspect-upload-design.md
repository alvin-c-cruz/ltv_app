# Inspect Upload Page — Design

**Date:** 2026-06-10
**Status:** Approved

## Purpose

A page in ltv_app where the user can upload arbitrary files (typically Excel)
into a known folder on the server so Claude Code can inspect them locally
(with openpyxl/pandas/Read). Works from any device on the LAN.

## Requirements

- Accept any file type, multiple files per upload.
- Files **accumulate** across uploads; a **Clear all** button empties the folder.
- Re-uploading a file with the same name overwrites the previous copy.
- Login required (same as the rest of the app).
- No database changes.

## Architecture

Extends the existing `upload` blueprint (`ltv_app/blueprints/upload/`),
which already has the multi-file upload pattern (`/upload/heroku`).

### Storage

`instance/uploads/inspect/` — created on first use, untracked by git.

### Routes (in `ltv_app/blueprints/upload/views.py`)

| Route | Methods | Behavior |
|---|---|---|
| `/upload/inspect` | GET | Render page: upload form + table of files in the inbox (name, size, modified time) + Clear all button. |
| `/upload/inspect` | POST | Save all selected files via `secure_filename` into the inbox folder; redirect back to the page. |
| `/upload/inspect/clear` | POST | Delete every file in the inbox folder; redirect back. |

Both routes use `@login_required`.

### Template

`ltv_app/blueprints/upload/pages/upload/inspect.html` — multi-file input,
Upload button, file listing table, Clear all button. Styled consistently
with existing pages (extends the app base template).

## Error handling

- Empty file selection on POST → no-op, redirect back.
- Filenames sanitized with `secure_filename`; entries that sanitize to an
  empty string are skipped.
- Clear-all path is fixed to the inbox folder only (no user-supplied paths).

## Testing

Functional test in `tests/functional/` using the `auth_client` fixture:

1. POST a file to `/upload/inspect` → file exists on disk and appears in the GET listing.
2. POST to `/upload/inspect/clear` → folder is empty and listing shows no files.
3. Unauthenticated access redirects to login.

## Workflow after upload

User uploads files, tells Claude "uploaded"; Claude reads
`instance/uploads/inspect/` directly.
