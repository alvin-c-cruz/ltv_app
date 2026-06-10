# Inspect Upload Page — Admin-Only Access & Menu Entry

**Date:** 2026-06-10
**Status:** Approved

## Purpose

Restrict the inspect upload page (`/upload/inspect`, added earlier today) to
admin users and surface it in the navbar for them. In this codebase "admin"
means `current_user.role == 'superuser'` (the role behind the navbar ADMIN
badge, the Workflow/Lock/Users menu items, and `@superuser_required`).

## Requirements

- `/upload/inspect` (GET/POST) and `/upload/inspect/clear` (POST) require the
  superuser role: anonymous users are redirected to login, authenticated
  non-superusers get 403.
- A new "Inspect Uploads" link appears in the **Other Records** navbar
  dropdown, inside the existing superuser-only block (with Lock and Users).
- No database changes.

## Changes

| File | Change |
|---|---|
| `ltv_app/blueprints/upload/views.py` | `@login_required` → `@superuser_required` on `inspect` and `inspect_clear`; import `superuser_required` from `..auth`. |
| `ltv_app/templates/navbar.html` | Add `<li><a href="{{ url_for('upload.inspect') }}">Inspect Uploads</a></li>` inside the superuser block of the Other Records dropdown. |
| `tests/functional/test_inspect_upload.py` | Switch fixtures from `auth_client` to `superuser_client`; add tests that a staff user gets 403 on both routes; keep anonymous-redirect tests. |

## Testing

- Existing 8 tests updated to `superuser_client` — all behaviors unchanged for admins.
- New: staff (`auth_client`) GET `/upload/inspect` → 403; staff POST `/upload/inspect/clear` → 403.
- Full functional suite passes.
