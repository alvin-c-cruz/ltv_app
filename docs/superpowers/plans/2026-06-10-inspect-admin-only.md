# Inspect Admin-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restrict `/upload/inspect` and `/upload/inspect/clear` to superusers and add an admin-only navbar entry.

**Architecture:** Swap the auth decorator on the two existing routes, add one navbar line inside the existing superuser-gated block, update tests to the `superuser_client` fixture.

**Tech Stack:** Flask, Jinja2, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-inspect-admin-only-design.md`

---

### Task 1: Tests first — admin-only access

**Files:**
- Modify: `tests/functional/test_inspect_upload.py`

- [ ] **Step 1: Update fixtures and add 403 tests**

Replace every `auth_client` parameter with `superuser_client` in the existing tests (the `_upload` helper is fixture-agnostic). Then append:

```python
def test_inspect_forbidden_for_staff(auth_client):
    response = auth_client.get('/upload/inspect')
    assert response.status_code == 403


def test_clear_forbidden_for_staff(auth_client):
    response = auth_client.post('/upload/inspect/clear')
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: the two new staff tests FAIL (routes currently allow any logged-in user → 302/200). All `superuser_client` tests PASS (superusers are logged-in users too).

- [ ] **Step 3: Tighten the routes**

In `ltv_app/blueprints/upload/views.py` change the import:

```python
from ..auth import login_required, superuser_required
```

and on both `inspect` and `inspect_clear`, replace `@login_required` with `@superuser_required`.

- [ ] **Step 4: Run the test file**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: ALL PASS (10 tests).

### Task 2: Navbar entry

**Files:**
- Modify: `ltv_app/templates/navbar.html`

- [ ] **Step 1: Add the link inside the superuser block of Other Records**

```html
{% if current_user.is_authenticated and current_user.role == 'superuser' %}
<li><a href="{{ url_for('lock.home') }}">Lock</a></li>
<li><a href="{{ url_for('users.home') }}">Users</a></li>
<li><a href="{{ url_for('upload.inspect') }}">Inspect Uploads</a></li>
{% endif %}
```

- [ ] **Step 2: Full functional suite**

Run: `pytest tests/functional/ -q`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/functional/test_inspect_upload.py ltv_app/blueprints/upload/views.py ltv_app/templates/navbar.html
git commit -m "Restrict inspect uploads to admin and add navbar entry"
```

### Task 3: Live verification

- [ ] Browser (already authenticated as admin from earlier session if still valid): confirm "Inspect Uploads" appears under Other Records and the page loads.
