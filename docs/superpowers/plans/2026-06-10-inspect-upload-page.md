# Inspect Upload Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A login-protected page at `/upload/inspect` where the user uploads arbitrary files into `instance/uploads/inspect/` so Claude can inspect them; files accumulate until a "Clear all" button empties the folder.

**Architecture:** Two routes added to the existing `upload` blueprint (`ltv_app/blueprints/upload/views.py`), one new Jinja2 template following the styling of `downloads.html`. The storage folder is resolved through a helper that honors the `INSPECT_UPLOAD_DIR` config key (used by tests for isolation) and defaults to `instance/uploads/inspect/`.

**Tech Stack:** Flask, Jinja2, pytest (functional tests with `auth_client` fixture from `tests/functional/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-06-10-inspect-upload-design.md`

---

## File Structure

- Modify: `tests/functional/conftest.py` — add `INSPECT_UPLOAD_DIR` to the test app config (isolated temp folder).
- Create: `tests/functional/test_inspect_upload.py` — functional tests.
- Modify: `ltv_app/blueprints/upload/views.py` — `_inspect_dir()` helper + `inspect` and `inspect_clear` routes.
- Create: `ltv_app/blueprints/upload/pages/upload/inspect.html` — upload form + file listing + clear button.

---

### Task 1: Isolate the inspect folder in tests

**Files:**
- Modify: `tests/functional/conftest.py` (the `app` fixture, ~line 199)

- [ ] **Step 1: Add `INSPECT_UPLOAD_DIR` to the test config**

In `tests/functional/conftest.py`, change the `create_app(...)` call inside the `app` fixture from:

```python
    flask_app = create_app({
        'DATABASE': str(db_path),
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
    })
```

to:

```python
    flask_app = create_app({
        'DATABASE': str(db_path),
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'INSPECT_UPLOAD_DIR': str(tmp_path / 'inspect_uploads'),
    })
```

- [ ] **Step 2: Run the existing functional suite to confirm nothing breaks**

Run: `pytest tests/functional/ -x -q`
Expected: same pass count as before the change (an unused config key changes nothing).

- [ ] **Step 3: Commit**

```bash
git add tests/functional/conftest.py
git commit -m "test: point inspect upload folder at temp dir in functional tests"
```

---

### Task 2: Upload + listing page (`GET/POST /upload/inspect`)

**Files:**
- Create: `tests/functional/test_inspect_upload.py`
- Modify: `ltv_app/blueprints/upload/views.py`
- Create: `ltv_app/blueprints/upload/pages/upload/inspect.html`

- [ ] **Step 1: Write the failing tests**

Create `tests/functional/test_inspect_upload.py`:

```python
"""Functional tests for the inspect upload page (/upload/inspect)."""
import io
import os


def _upload(client, filename, content=b'dummy-bytes'):
    return client.post(
        '/upload/inspect',
        data={'file[]': (io.BytesIO(content), filename)},
        content_type='multipart/form-data',
    )


def test_inspect_requires_login(client):
    response = client.get('/upload/inspect')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_get_inspect_page_empty(auth_client):
    response = auth_client.get('/upload/inspect')
    assert response.status_code == 200
    assert b'No files uploaded yet' in response.data


def test_upload_saves_file_and_lists_it(app, auth_client):
    response = _upload(auth_client, 'report.xlsx', b'excel-bytes')
    assert response.status_code == 302

    saved = os.path.join(app.config['INSPECT_UPLOAD_DIR'], 'report.xlsx')
    assert os.path.isfile(saved)
    with open(saved, 'rb') as f:
        assert f.read() == b'excel-bytes'

    page = auth_client.get('/upload/inspect')
    assert b'report.xlsx' in page.data


def test_uploads_accumulate(app, auth_client):
    _upload(auth_client, 'first.csv')
    _upload(auth_client, 'second.pdf')

    folder = app.config['INSPECT_UPLOAD_DIR']
    assert sorted(os.listdir(folder)) == ['first.csv', 'second.pdf']

    page = auth_client.get('/upload/inspect')
    assert b'first.csv' in page.data
    assert b'second.pdf' in page.data


def test_same_name_overwrites(app, auth_client):
    _upload(auth_client, 'data.xlsx', b'version-1')
    _upload(auth_client, 'data.xlsx', b'version-2')

    folder = app.config['INSPECT_UPLOAD_DIR']
    assert os.listdir(folder) == ['data.xlsx']
    with open(os.path.join(folder, 'data.xlsx'), 'rb') as f:
        assert f.read() == b'version-2'


def test_empty_post_is_noop(app, auth_client):
    response = auth_client.post(
        '/upload/inspect', data={}, content_type='multipart/form-data'
    )
    assert response.status_code == 302
    assert os.listdir(app.config['INSPECT_UPLOAD_DIR']) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: all tests FAIL with 404 responses (route doesn't exist). `test_inspect_requires_login` fails because a 404 is returned instead of a 302.

- [ ] **Step 3: Implement the route and helper**

In `ltv_app/blueprints/upload/views.py`:

Add `url_for` to the flask import (line 1) and `datetime` below it:

```python
from flask import Blueprint, render_template, request, current_app, redirect, jsonify, send_from_directory, abort, url_for
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from openpyxl import load_workbook
from dataclasses import dataclass
```

Below the `download_file` view, add:

```python
def _inspect_dir():
    """Folder where files uploaded for Claude inspection are stored."""
    path = current_app.config.get(
        'INSPECT_UPLOAD_DIR',
        os.path.join(current_app.instance_path, 'uploads', 'inspect'),
    )
    os.makedirs(path, exist_ok=True)
    return path


@bp.route('/inspect', methods=["GET", "POST"])
@login_required
def inspect():
    inspect_dir = _inspect_dir()

    if request.method == "POST":
        for file in request.files.getlist("file[]"):
            filename = secure_filename(file.filename)
            if filename:
                file.save(os.path.join(inspect_dir, filename))
        return redirect(url_for('upload.inspect'))

    files = []
    for name in sorted(os.listdir(inspect_dir)):
        full_path = os.path.join(inspect_dir, name)
        if not os.path.isfile(full_path):
            continue
        stat = os.stat(full_path)
        files.append({
            'name': name,
            'size_kb': f"{stat.st_size / 1024:,.1f}",
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
        })
    return render_template('upload/inspect.html', files=files)
```

- [ ] **Step 4: Create the template**

Create `ltv_app/blueprints/upload/pages/upload/inspect.html` (styled after `downloads.html`):

```html
{% extends 'base.html' %}

{% block content %}
<h1>Inspect Uploads</h1>
<p style="color:var(--text-muted)">Upload files here for Claude to inspect. Files stay until you clear them.</p>

<form method="post" action="{{ url_for('upload.inspect') }}" enctype="multipart/form-data" style="margin-top:1rem">
    <input type="file" name="file[]" multiple class="form-control" style="display:inline-block; width:auto">
    <input type="submit" value="Upload" class="btn btn-success">
</form>

<div class="table-wrap" style="margin-top:1.25rem">
    {% if files %}
    <table class="table" style="table-layout:fixed; width:100%">
        <colgroup>
            <col style="width:60%">
            <col style="width:20%">
            <col style="width:20%">
        </colgroup>
        <thead>
            <tr>
                <th>Filename</th>
                <th class="text-center">Size (KB)</th>
                <th class="text-center">Uploaded</th>
            </tr>
        </thead>
        <tbody>
        {% for file in files %}
        <tr>
            <td>{{ file.name }}</td>
            <td class="text-center">{{ file.size_kb }}</td>
            <td class="text-center">{{ file.modified }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    <form method="post" action="{{ url_for('upload.inspect_clear') }}" style="margin-top:1rem">
        <input type="submit" value="Clear all" class="btn btn-outline"
               onclick="return confirm('Delete all uploaded files?');">
    </form>
    {% else %}
    <p style="color:var(--text-muted)">No files uploaded yet.</p>
    {% endif %}
</div>
{% endblock %}
```

Note: the template references `upload.inspect_clear` only inside `{% if files %}`, so the empty-state GET works before Task 3 — but `test_upload_saves_file_and_lists_it` will fail on the listing render until the `inspect_clear` route exists. That is expected; Task 3 makes it pass. To keep Task 2 independently green, Task 3's route is included in the same commit window — run the full file's tests at the end of Task 3.

- [ ] **Step 5: Run tests**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: `test_inspect_requires_login`, `test_get_inspect_page_empty`, `test_empty_post_is_noop` PASS. Tests that render the non-empty listing (`test_upload_saves_file_and_lists_it`, `test_uploads_accumulate`, `test_same_name_overwrites`) FAIL with `BuildError: Could not build url for endpoint 'upload.inspect_clear'` — proceed to Task 3 which fixes this.

---

### Task 3: Clear-all route (`POST /upload/inspect/clear`)

**Files:**
- Modify: `tests/functional/test_inspect_upload.py`
- Modify: `ltv_app/blueprints/upload/views.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/functional/test_inspect_upload.py`:

```python
def test_clear_removes_all_files(app, auth_client):
    _upload(auth_client, 'a.xlsx')
    _upload(auth_client, 'b.xlsx')

    response = auth_client.post('/upload/inspect/clear')
    assert response.status_code == 302

    assert os.listdir(app.config['INSPECT_UPLOAD_DIR']) == []
    page = auth_client.get('/upload/inspect')
    assert b'No files uploaded yet' in page.data


def test_clear_requires_login(client):
    response = client.post('/upload/inspect/clear')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: both new tests FAIL — the route doesn't exist yet, so both requests return 404 (`test_clear_requires_login` expects 302, `test_clear_removes_all_files` expects 302 and an empty folder).

- [ ] **Step 3: Implement the clear route**

In `ltv_app/blueprints/upload/views.py`, below the `inspect` view:

```python
@bp.route('/inspect/clear', methods=["POST"])
@login_required
def inspect_clear():
    inspect_dir = _inspect_dir()
    for name in os.listdir(inspect_dir):
        full_path = os.path.join(inspect_dir, name)
        if os.path.isfile(full_path):
            os.remove(full_path)
    return redirect(url_for('upload.inspect'))
```

- [ ] **Step 4: Run the full test file**

Run: `pytest tests/functional/test_inspect_upload.py -v`
Expected: ALL tests PASS (including the three left failing at the end of Task 2).

- [ ] **Step 5: Run the whole functional suite**

Run: `pytest tests/functional/ -q`
Expected: all PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add tests/functional/test_inspect_upload.py ltv_app/blueprints/upload/views.py "ltv_app/blueprints/upload/pages/upload/inspect.html"
git commit -m "feat: add /upload/inspect page for uploading files for Claude inspection"
```

---

### Task 4: Verify in the running app

**Files:** none (manual verification)

- [ ] **Step 1: Restart/confirm dev server**

The dev server (`python flask_app.py`) runs with debug auto-reload, so the new route is live after saving. Confirm: `Invoke-WebRequest http://192.168.1.48:5000/upload/inspect` returns 302 to login (unauthenticated).

- [ ] **Step 2: Browser verification with Playwright MCP**

Log in via the browser, navigate to `/upload/inspect`, upload a sample file, confirm it appears in the listing, and confirm it exists at `instance/uploads/inspect/`. Click Clear all and confirm the folder empties.
