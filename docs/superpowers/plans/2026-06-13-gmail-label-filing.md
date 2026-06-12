# Gmail Label Filing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Bank free-text column with a Gmail-label-backed dropdown, add a dependent Sub-label dropdown column, and add a File button that applies the sub-label and archives the thread.

**Architecture:** `list_labels()` and `apply_label_and_archive()` in `gmail_client.py` handle all Gmail API calls. `views.py` adds a new `tbl_gmail_thread_labels` table and four route changes: updated `inbox()`, new `GET /labels`, updated `PATCH /bank`, new `PATCH /sublabel`, new `POST /file`. The label hierarchy is embedded in the page as `var LABELS` JSON; dropdowns are built client-side with no extra fetch.

**Tech Stack:** Python/Flask, SQLite (`get_db()`), Gmail API (`google-api-python-client`), vanilla JS.

---

### Task 1: `gmail_client.py` — `list_labels()` and `apply_label_and_archive()` (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/extensions/gmail_client.py`
- Test: `tests/functional/test_gmail_client.py`

`list_labels()` is the only function with meaningful logic to unit-test (filtering + hierarchy building). `apply_label_and_archive()` is a thin API wrapper; it is tested at the route level in Task 3.

- [ ] **Step 1: Append 3 failing unit tests to `tests/functional/test_gmail_client.py`**

```python
# ── list_labels ───────────────────────────────────────────────────────────────

def test_list_labels_filters_alvin_prefix():
    from unittest.mock import MagicMock, patch
    from ltv_app.blueprints.gmail.extensions.gmail_client import list_labels

    mock_svc = MagicMock()
    mock_svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        'labels': [
            {'id': 'L1', 'name': 'Alvin - SHK'},
            {'id': 'L2', 'name': 'Alvin - SHK/Statements'},
            {'id': 'L3', 'name': 'INBOX'},
            {'id': 'L4', 'name': 'Other Label'},
        ]
    }
    with patch('ltv_app.blueprints.gmail.extensions.gmail_client._get_service', return_value=mock_svc):
        result = list_labels()
    names = [p['name'] for p in result]
    assert 'Alvin - SHK' in names
    assert 'INBOX' not in names
    assert 'Other Label' not in names


def test_list_labels_builds_hierarchy():
    from unittest.mock import MagicMock, patch
    from ltv_app.blueprints.gmail.extensions.gmail_client import list_labels

    mock_svc = MagicMock()
    mock_svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        'labels': [
            {'id': 'L1', 'name': 'Alvin - SHK'},
            {'id': 'L2', 'name': 'Alvin - SHK/Statements'},
            {'id': 'L3', 'name': 'Alvin - SHK/Trades'},
            {'id': 'L4', 'name': 'Alvin - DB'},
        ]
    }
    with patch('ltv_app.blueprints.gmail.extensions.gmail_client._get_service', return_value=mock_svc):
        result = list_labels()
    shk = next(p for p in result if p['name'] == 'Alvin - SHK')
    child_ids = [c['id'] for c in shk['children']]
    assert 'L2' in child_ids
    assert 'L3' in child_ids
    db = next(p for p in result if p['name'] == 'Alvin - DB')
    assert db['children'] == []


def test_list_labels_short_names():
    from unittest.mock import MagicMock, patch
    from ltv_app.blueprints.gmail.extensions.gmail_client import list_labels

    mock_svc = MagicMock()
    mock_svc.users.return_value.labels.return_value.list.return_value.execute.return_value = {
        'labels': [
            {'id': 'L1', 'name': 'Alvin - SHK'},
            {'id': 'L2', 'name': 'Alvin - SHK/Statements'},
        ]
    }
    with patch('ltv_app.blueprints.gmail.extensions.gmail_client._get_service', return_value=mock_svc):
        result = list_labels()
    parent = result[0]
    assert parent['short'] == 'SHK'
    assert parent['children'][0]['short'] == 'Statements'
```

- [ ] **Step 2: Run tests to confirm all 3 fail**

```
pytest tests/functional/test_gmail_client.py::test_list_labels_filters_alvin_prefix tests/functional/test_gmail_client.py::test_list_labels_builds_hierarchy tests/functional/test_gmail_client.py::test_list_labels_short_names -v
```

Expected: all 3 FAIL (ImportError — `list_labels` not defined).

- [ ] **Step 3: Add `list_labels()` and `apply_label_and_archive()` to `gmail_client.py`**

Append to the end of `ltv_app/blueprints/gmail/extensions/gmail_client.py`:

```python
def list_labels():
    """Return Alvin- parent labels with their nested children."""
    service = _get_service()
    result = service.users().labels().list(userId='me').execute()
    all_labels = result.get('labels', [])

    prefix = 'Alvin - '
    alvin = [l for l in all_labels if l['name'].startswith(prefix)]

    parents = {}
    for label in alvin:
        remainder = label['name'][len(prefix):]
        if '/' not in remainder:
            parents[label['name']] = {
                'id': label['id'],
                'name': label['name'],
                'short': remainder,
                'children': [],
            }

    for label in alvin:
        remainder = label['name'][len(prefix):]
        if '/' in remainder:
            parent_short, child_short = remainder.split('/', 1)
            parent_name = prefix + parent_short
            if parent_name in parents:
                parents[parent_name]['children'].append({
                    'id': label['id'],
                    'name': label['name'],
                    'short': child_short,
                })

    return list(parents.values())


def apply_label_and_archive(thread_id, label_id):
    """Apply a label to a thread and remove it from INBOX."""
    service = _get_service()
    service.users().threads().modify(
        userId='me',
        id=thread_id,
        body={'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}
    ).execute()
```

- [ ] **Step 4: Run the 3 new tests to confirm they pass**

```
pytest tests/functional/test_gmail_client.py::test_list_labels_filters_alvin_prefix tests/functional/test_gmail_client.py::test_list_labels_builds_hierarchy tests/functional/test_gmail_client.py::test_list_labels_short_names -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run full client test suite**

```
pytest tests/functional/test_gmail_client.py -v
```

Expected: all 15 tests PASS (was 12, now 15).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/gmail/extensions/gmail_client.py tests/functional/test_gmail_client.py
git commit -m "Add list_labels() and apply_label_and_archive() to gmail_client"
```

---

### Task 2: `views.py` — DB helpers, updated `inbox()`, `GET /labels`, updated `PATCH /bank` (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/views.py`
- Test: `tests/functional/test_gmail.py`

The existing 6 `test_bank_patch_*` tests send `{"bank_label": "SHK"}`. The updated route accepts `{"bank_id": "Label_123"}`. Update those tests first (they will fail), then replace `views.py`.

- [ ] **Step 1: Update the 6 existing bank tests in `tests/functional/test_gmail.py`**

Find and replace each occurrence. The full updated versions:

```python
def test_bank_patch_success(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': 'Label_123'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    assert response.get_json() == {}


def test_bank_patch_clear(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': ''},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200


def test_bank_patch_missing_key(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_bank_patch_requires_superuser(auth_client):
    response = auth_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': 'Label_123'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 403


def test_bank_patch_requires_xhr(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': 'Label_123'}
    )
    assert response.status_code == 403
    assert response.get_json()['error'] == 'Forbidden'


def test_bank_patch_unauthenticated(client):
    response = client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': 'Label_123'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
```

- [ ] **Step 2: Append 3 new tests to `tests/functional/test_gmail.py`**

```python
# ── GET /gmail/labels ─────────────────────────────────────────────────────────

def test_labels_route_returns_json(superuser_client):
    from unittest.mock import patch
    with patch('ltv_app.blueprints.gmail.views.list_labels', return_value=[
        {'id': 'L1', 'name': 'Alvin - SHK', 'short': 'SHK', 'children': []}
    ]):
        response = superuser_client.get('/gmail/labels')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert data[0]['short'] == 'SHK'


def test_labels_route_requires_superuser(auth_client):
    response = auth_client.get('/gmail/labels')
    assert response.status_code == 403


# ── bank patch clears sublabel ────────────────────────────────────────────────

def test_bank_patch_clears_sublabel(superuser_client, db_conn):
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS tbl_gmail_thread_labels (
            thread_id TEXT PRIMARY KEY, bank_id TEXT, sublabel_id TEXT
        )
    ''')
    db_conn.execute(
        'INSERT OR REPLACE INTO tbl_gmail_thread_labels VALUES (?, ?, ?)',
        ('abc123', 'Label_1', 'Label_2')
    )
    db_conn.commit()
    superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_id': 'Label_3'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    row = db_conn.execute(
        'SELECT sublabel_id FROM tbl_gmail_thread_labels WHERE thread_id = ?',
        ('abc123',)
    ).fetchone()
    assert row is not None
    assert row[0] is None
```

- [ ] **Step 3: Run all 9 tests to confirm they fail**

```
pytest tests/functional/test_gmail.py::test_bank_patch_success tests/functional/test_gmail.py::test_bank_patch_clear tests/functional/test_gmail.py::test_bank_patch_missing_key tests/functional/test_gmail.py::test_bank_patch_requires_superuser tests/functional/test_gmail.py::test_bank_patch_requires_xhr tests/functional/test_gmail.py::test_bank_patch_unauthenticated tests/functional/test_gmail.py::test_labels_route_returns_json tests/functional/test_gmail.py::test_labels_route_requires_superuser tests/functional/test_gmail.py::test_bank_patch_clears_sublabel -v
```

Expected: all 9 FAIL (bank tests get 400 wrong key; labels route gets 404; clears_sublabel fails because old route writes to old table).

- [ ] **Step 4: Replace the entire content of `ltv_app/blueprints/gmail/views.py`**

```python
from flask import Blueprint, render_template, jsonify, flash, request
from flask_login import login_required
from googleapiclient.errors import HttpError

from ..auth import superuser_required
from ..database import get_db
from .extensions.gmail_client import (
    list_threads, get_thread, trash_thread,
    list_labels, apply_label_and_archive,
)

bp = Blueprint('gmail', __name__, template_folder='pages', url_prefix='/gmail')


def _ensure_labels_table(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS tbl_gmail_thread_labels (
            thread_id   TEXT PRIMARY KEY,
            bank_id     TEXT,
            sublabel_id TEXT
        )
    ''')
    db.commit()


def _get_stored_labels(db, thread_ids):
    if not thread_ids:
        return {}
    placeholders = ','.join('?' * len(thread_ids))
    rows = db.execute(
        f'SELECT thread_id, bank_id, sublabel_id FROM tbl_gmail_thread_labels '
        f'WHERE thread_id IN ({placeholders})',
        thread_ids
    ).fetchall()
    return {row[0]: {'bank_id': row[1], 'sublabel_id': row[2]} for row in rows}


def _short_map(label_tree):
    m = {}
    for parent in label_tree:
        m[parent['id']] = parent['short']
        for child in parent['children']:
            m[child['id']] = child['short']
    return m


@bp.route('/inbox')
@login_required
@superuser_required
def inbox():
    try:
        threads = list_threads(max_results=20)
        label_tree = list_labels()
    except (FileNotFoundError, ValueError):
        return render_template('gmail/inbox.html', threads=None, not_configured=True, labels=[])
    except HttpError as e:
        flash(f'Gmail API error: {e}', 'danger')
        return render_template('gmail/inbox.html', threads=[], not_configured=False, labels=[])
    db = get_db()
    _ensure_labels_table(db)
    stored = _get_stored_labels(db, [t['id'] for t in threads])
    short = _short_map(label_tree)
    for t in threads:
        s = stored.get(t['id'], {})
        bank_id = s.get('bank_id') or ''
        sublabel_id = s.get('sublabel_id') or ''
        t['bank_id'] = bank_id
        t['sublabel_id'] = sublabel_id
        t['bank'] = short.get(bank_id, '—') if bank_id else '—'
        t['sublabel'] = short.get(sublabel_id, '—') if sublabel_id else '—'
    return render_template('gmail/inbox.html', threads=threads, not_configured=False,
                           labels=label_tree)


@bp.route('/labels')
@login_required
@superuser_required
def labels_view():
    try:
        result = list_labels()
    except (FileNotFoundError, ValueError):
        return jsonify({'error': 'Gmail not configured'}), 503
    except HttpError as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(result)


@bp.route('/thread/<thread_id>')
@login_required
@superuser_required
def thread(thread_id):
    try:
        messages = get_thread(thread_id)
    except (FileNotFoundError, ValueError):
        return jsonify({'error': 'Gmail not configured'}), 503
    except HttpError as e:
        if e.resp.status == 404:
            return jsonify({'error': 'Thread not found'}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'messages': messages})


@bp.route('/thread/<thread_id>/trash', methods=['POST'])
@login_required
@superuser_required
def trash_thread_view(thread_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'error': 'Forbidden'}), 403
    try:
        trash_thread(thread_id)
    except (FileNotFoundError, ValueError):
        return jsonify({'error': 'Gmail not configured'}), 503
    except HttpError as e:
        if e.resp.status == 404:
            return jsonify({'error': 'Thread not found'}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({}), 200


@bp.route('/thread/<thread_id>/bank', methods=['PATCH'])
@login_required
@superuser_required
def update_bank(thread_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True)
    if data is None or 'bank_id' not in data:
        return jsonify({'error': 'Missing bank_id'}), 400
    bank_id = data['bank_id'].strip()
    db = get_db()
    _ensure_labels_table(db)
    if bank_id:
        db.execute(
            'INSERT OR REPLACE INTO tbl_gmail_thread_labels '
            '(thread_id, bank_id, sublabel_id) VALUES (?, ?, NULL)',
            (thread_id, bank_id)
        )
    else:
        db.execute('DELETE FROM tbl_gmail_thread_labels WHERE thread_id = ?', (thread_id,))
    db.commit()
    return jsonify({}), 200
```

- [ ] **Step 5: Run the 9 tests to confirm they pass**

```
pytest tests/functional/test_gmail.py::test_bank_patch_success tests/functional/test_gmail.py::test_bank_patch_clear tests/functional/test_gmail.py::test_bank_patch_missing_key tests/functional/test_gmail.py::test_bank_patch_requires_superuser tests/functional/test_gmail.py::test_bank_patch_requires_xhr tests/functional/test_gmail.py::test_bank_patch_unauthenticated tests/functional/test_gmail.py::test_labels_route_returns_json tests/functional/test_gmail.py::test_labels_route_requires_superuser tests/functional/test_gmail.py::test_bank_patch_clears_sublabel -v
```

Expected: all 9 PASS.

- [ ] **Step 6: Run full Gmail test suite**

```
pytest tests/functional/test_gmail.py tests/functional/test_gmail_client.py -v
```

Expected: all tests PASS (some pre-existing tests mock `list_threads` — those still pass unchanged).

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/gmail/views.py tests/functional/test_gmail.py
git commit -m "Add labels route, update bank route to use Gmail label IDs, add tbl_gmail_thread_labels"
```

---

### Task 3: `views.py` — `PATCH /sublabel` and `POST /file` routes (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/views.py`
- Test: `tests/functional/test_gmail.py`

- [ ] **Step 1: Append 9 failing tests to `tests/functional/test_gmail.py`**

```python
# ── PATCH /gmail/thread/<id>/sublabel ────────────────────────────────────────

def test_sublabel_patch_success(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/sublabel',
        json={'sublabel_id': 'Label_456'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    assert response.get_json() == {}


def test_sublabel_patch_missing_key(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/sublabel',
        json={},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 400
    assert 'error' in response.get_json()


def test_sublabel_patch_requires_superuser(auth_client):
    response = auth_client.patch(
        '/gmail/thread/abc123/sublabel',
        json={'sublabel_id': 'Label_456'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 403


def test_sublabel_patch_requires_xhr(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/sublabel',
        json={'sublabel_id': 'Label_456'}
    )
    assert response.status_code == 403
    assert response.get_json()['error'] == 'Forbidden'


# ── POST /gmail/thread/<id>/file ──────────────────────────────────────────────

def test_file_success(superuser_client, db_conn):
    from unittest.mock import patch
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS tbl_gmail_thread_labels (
            thread_id TEXT PRIMARY KEY, bank_id TEXT, sublabel_id TEXT
        )
    ''')
    db_conn.execute(
        'INSERT OR REPLACE INTO tbl_gmail_thread_labels VALUES (?, ?, ?)',
        ('abc123', 'Label_1', 'Label_456')
    )
    db_conn.commit()
    with patch('ltv_app.blueprints.gmail.views.apply_label_and_archive') as mock_file:
        response = superuser_client.post(
            '/gmail/thread/abc123/file',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
    assert response.status_code == 200
    mock_file.assert_called_once_with('abc123', 'Label_456')


def test_file_no_sublabel_returns_400(superuser_client):
    response = superuser_client.post(
        '/gmail/thread/abc123/file',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == 'No sub-label set'


def test_file_requires_superuser(auth_client):
    response = auth_client.post(
        '/gmail/thread/abc123/file',
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 403


def test_file_requires_xhr(superuser_client):
    response = superuser_client.post('/gmail/thread/abc123/file')
    assert response.status_code == 403
    assert response.get_json()['error'] == 'Forbidden'


def test_file_thread_not_found_returns_404(superuser_client, db_conn):
    from unittest.mock import patch, MagicMock
    from googleapiclient.errors import HttpError
    db_conn.execute('''
        CREATE TABLE IF NOT EXISTS tbl_gmail_thread_labels (
            thread_id TEXT PRIMARY KEY, bank_id TEXT, sublabel_id TEXT
        )
    ''')
    db_conn.execute(
        'INSERT OR REPLACE INTO tbl_gmail_thread_labels VALUES (?, ?, ?)',
        ('abc123', 'Label_1', 'Label_456')
    )
    db_conn.commit()
    mock_resp = MagicMock()
    mock_resp.status = 404
    with patch('ltv_app.blueprints.gmail.views.apply_label_and_archive',
               side_effect=HttpError(mock_resp, b'')):
        response = superuser_client.post(
            '/gmail/thread/abc123/file',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to confirm all 9 fail**

```
pytest tests/functional/test_gmail.py::test_sublabel_patch_success tests/functional/test_gmail.py::test_sublabel_patch_missing_key tests/functional/test_gmail.py::test_sublabel_patch_requires_superuser tests/functional/test_gmail.py::test_sublabel_patch_requires_xhr tests/functional/test_gmail.py::test_file_success tests/functional/test_gmail.py::test_file_no_sublabel_returns_400 tests/functional/test_gmail.py::test_file_requires_superuser tests/functional/test_gmail.py::test_file_requires_xhr tests/functional/test_gmail.py::test_file_thread_not_found_returns_404 -v
```

Expected: all 9 FAIL (404 — routes not found).

- [ ] **Step 3: Append the two new routes to `ltv_app/blueprints/gmail/views.py`**

Add after the `update_bank` route at the end of the file:

```python
@bp.route('/thread/<thread_id>/sublabel', methods=['PATCH'])
@login_required
@superuser_required
def update_sublabel(thread_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'error': 'Forbidden'}), 403
    data = request.get_json(silent=True)
    if data is None or 'sublabel_id' not in data:
        return jsonify({'error': 'Missing sublabel_id'}), 400
    sublabel_id = data['sublabel_id'].strip()
    db = get_db()
    _ensure_labels_table(db)
    if sublabel_id:
        db.execute(
            'INSERT OR IGNORE INTO tbl_gmail_thread_labels '
            '(thread_id, bank_id, sublabel_id) VALUES (?, NULL, NULL)',
            (thread_id,)
        )
        db.execute(
            'UPDATE tbl_gmail_thread_labels SET sublabel_id = ? WHERE thread_id = ?',
            (sublabel_id, thread_id)
        )
    else:
        db.execute(
            'UPDATE tbl_gmail_thread_labels SET sublabel_id = NULL WHERE thread_id = ?',
            (thread_id,)
        )
    db.commit()
    return jsonify({}), 200


@bp.route('/thread/<thread_id>/file', methods=['POST'])
@login_required
@superuser_required
def file_thread(thread_id):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return jsonify({'error': 'Forbidden'}), 403
    db = get_db()
    _ensure_labels_table(db)
    row = db.execute(
        'SELECT sublabel_id FROM tbl_gmail_thread_labels WHERE thread_id = ?',
        (thread_id,)
    ).fetchone()
    if not row or not row[0]:
        return jsonify({'error': 'No sub-label set'}), 400
    sublabel_id = row[0]
    try:
        apply_label_and_archive(thread_id, sublabel_id)
    except (FileNotFoundError, ValueError):
        return jsonify({'error': 'Gmail not configured'}), 503
    except HttpError as e:
        if e.resp.status == 404:
            return jsonify({'error': 'Thread not found'}), 404
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({}), 200
```

- [ ] **Step 4: Run the 9 new tests to confirm they pass**

```
pytest tests/functional/test_gmail.py::test_sublabel_patch_success tests/functional/test_gmail.py::test_sublabel_patch_missing_key tests/functional/test_gmail.py::test_sublabel_patch_requires_superuser tests/functional/test_gmail.py::test_sublabel_patch_requires_xhr tests/functional/test_gmail.py::test_file_success tests/functional/test_gmail.py::test_file_no_sublabel_returns_400 tests/functional/test_gmail.py::test_file_requires_superuser tests/functional/test_gmail.py::test_file_requires_xhr tests/functional/test_gmail.py::test_file_thread_not_found_returns_404 -v
```

Expected: all 9 PASS.

- [ ] **Step 5: Run full Gmail test suite**

```
pytest tests/functional/test_gmail.py tests/functional/test_gmail_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/gmail/views.py tests/functional/test_gmail.py
git commit -m "Add PATCH /sublabel and POST /file routes for Gmail label filing"
```

---

### Task 4: `inbox.html` — Bank dropdown, Sub-label column, File button (frontend)

**Files:**
- Modify: `ltv_app/blueprints/gmail/pages/gmail/inbox.html`

No automated tests — verify in browser. The backend already passes `labels` (a list) and updated thread dicts with `bank_id`, `sublabel_id`, `bank`, `sublabel` keys.

- [ ] **Step 1: Replace the entire content of `ltv_app/blueprints/gmail/pages/gmail/inbox.html`**

```html
{% extends 'base.html' %}

{% block content %}
<style>
@media (max-width: 1024px) {
  #inbox-table { table-layout: fixed; width: 100%; }
  #inbox-table th:nth-child(6),
  #inbox-table td:nth-child(6),
  #inbox-table th:last-child,
  #inbox-table td:last-child { display: none; }
  #inbox-table th:nth-child(1) { width: 8% !important; }
  #inbox-table th:nth-child(2) { width: 12% !important; }
  #inbox-table th:nth-child(3) { width: 28% !important; }
  #inbox-table th:nth-child(4) { width: 36% !important; }
  #inbox-table th:nth-child(5) { width: 16% !important; }
  #inbox-table td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
</style>
<h1>Gmail Inbox</h1>
<p style="color:var(--text-muted)">larrylilia@gmail.com — 20 most recent threads</p>

{% with messages = get_flashed_messages(with_categories=true) %}
  {% for category, message in messages %}
  <div class="alert alert-{{ category }}" style="margin-top:1rem">{{ message }}</div>
  {% endfor %}
{% endwith %}

{% if not_configured %}
<div class="alert alert-warning" style="margin-top:1.25rem">
  <strong>Gmail not configured.</strong>
  Run <code>python instance/gmail_setup.py</code> to set up OAuth access, then reload this page.
</div>

{% elif threads is not none %}
{# ── Right-click context menu ──────────────────────────────────── #}
<div id="ctx-menu" style="display:none;position:fixed;z-index:500;background:#fff;
     border:1px solid var(--border-color,#dee2e6);border-radius:4px;
     box-shadow:0 2px 8px rgba(0,0,0,.15);min-width:160px">
  <div id="ctx-open"
       style="padding:.5rem 1rem;cursor:pointer"
       onmouseover="this.style.background='var(--bg-secondary,#f8f9fa)'"
       onmouseout="this.style.background=''">Open in Gmail ↗</div>
  <div id="ctx-trash"
       style="padding:.5rem 1rem;cursor:pointer;color:var(--danger,#dc3545)"
       onmouseover="this.style.background='var(--bg-secondary,#f8f9fa)'"
       onmouseout="this.style.background=''">Move to Trash</div>
</div>
<div class="table-wrap" style="margin-top:1.25rem">
  <table class="table" id="inbox-table">
    <thead>
      <tr>
        <th style="width:8%">Bank</th>
        <th style="width:10%">Sub-label</th>
        <th style="width:22%">From</th>
        <th style="width:26%">Subject</th>
        <th style="width:10%">Date</th>
        <th style="width:4%"></th>
        <th style="width:20%">Snippet</th>
      </tr>
    </thead>
    <tbody>
    {% for thread in threads %}
      <tr class="inbox-row" data-thread-id="{{ thread.id }}" style="cursor:pointer">
        <td class="bank-cell"
            data-thread-id="{{ thread.id }}"
            data-bank-id="{{ thread.bank_id }}"
            style="font-weight:500;font-size:0.8rem;cursor:pointer">{{ thread.bank }}</td>
        <td class="sublabel-cell"
            data-thread-id="{{ thread.id }}"
            data-sublabel-id="{{ thread.sublabel_id }}"
            style="font-size:0.8rem;cursor:pointer">{{ thread.sublabel }}</td>
        <td>{{ thread.sender }}</td>
        <td>{{ thread.subject }}</td>
        <td>{{ thread.date }}</td>
        <td class="file-cell" style="text-align:center;padding:0 2px">
          <button class="file-btn btn btn-sm btn-primary"
                  data-thread-id="{{ thread.id }}"
                  style="padding:1px 6px;font-size:0.75rem;{% if not thread.sublabel_id %}display:none{% endif %}">→</button>
        </td>
        <td style="color:var(--text-muted);font-size:0.875rem">{{ thread.snippet }}</td>
      </tr>
      <tr class="thread-expand" id="expand-{{ thread.id }}" style="display:none">
        <td colspan="7">
          <div class="thread-messages"
               style="padding:0.75rem 1rem;background:var(--bg-secondary,#f8f9fa);border-radius:4px">
          </div>
        </td>
      </tr>
    {% else %}
      <tr>
        <td colspan="7" style="text-align:center;color:var(--text-muted);padding:2rem">
          No threads found.
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
{# ── Trash confirmation modal ──────────────────────────────────── #}
<div class="modal-overlay" id="trashModal"
     onclick="if(event.target===this)closeTrashModal()">
  <div class="modal">
    <div class="modal-header">
      <span class="modal-title">Move to Trash</span>
      <button type="button" class="modal-close"
              onclick="closeTrashModal()">&times;</button>
    </div>
    <div style="padding:16px 20px">
      <p style="margin:0 0 .75rem">Move this thread to Trash?</p>
      <div id="trash-error"
           style="display:none;color:var(--danger,#dc3545);margin-bottom:.75rem"></div>
      <div style="display:flex;gap:.5rem;justify-content:flex-end">
        <button type="button" class="btn btn-secondary"
                onclick="closeTrashModal()">Cancel</button>
        <button type="button" class="btn btn-danger"
                id="trash-confirm-btn"
                onclick="confirmTrash()">Move to Trash</button>
      </div>
    </div>
  </div>
</div>
{% endif %}

<script>
var LABELS = {{ labels|tojson }};

// ── Thread expand ─────────────────────────────────────────────────
(function () {
  var activeId = null;

  document.querySelectorAll('.inbox-row').forEach(function (row) {
    row.addEventListener('click', function () {
      var id = this.dataset.threadId;
      var expandRow = document.getElementById('expand-' + id);
      var msgDiv = expandRow.querySelector('.thread-messages');

      if (activeId && activeId !== id) {
        document.getElementById('expand-' + activeId).style.display = 'none';
      }
      if (activeId === id) {
        expandRow.style.display = 'none';
        activeId = null;
        return;
      }
      activeId = id;
      expandRow.style.display = '';
      msgDiv.innerHTML = '<em style="color:var(--text-muted)">Loading…</em>';

      fetch('/gmail/thread/' + id)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) {
            msgDiv.innerHTML = '<span style="color:var(--danger,red)">Error: ' + esc(data.error) + '</span>';
            return;
          }
          var html = '';
          data.messages.forEach(function (msg) {
            html += '<div style="border-bottom:1px solid var(--border-color,#dee2e6);'
                  + 'padding:0.6rem 0;margin-bottom:0.4rem">';
            html += '<strong>' + esc(msg.sender) + '</strong>';
            html += ' &nbsp;&middot;&nbsp; '
                  + '<span style="color:var(--text-muted);font-size:0.8rem">' + esc(msg.date) + '</span>';
            html += '<div style="margin-top:0.4rem;white-space:pre-wrap;font-size:0.875rem">'
                  + esc(msg.body || '(no body)') + '</div>';
            html += '</div>';
          });
          msgDiv.innerHTML = html;
        })
        .catch(function () {
          msgDiv.innerHTML = '<span style="color:var(--danger,red)">Failed to load thread.</span>';
        });
    });
  });

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
}());

// ── Context menu ──────────────────────────────────────────────────
(function () {
  var ctxMenu = document.getElementById('ctx-menu');
  var ctxThreadId = null;

  document.addEventListener('contextmenu', function (e) {
    if (document.getElementById('trashModal').classList.contains('active')) return;
    var row = e.target.closest('.inbox-row');
    if (!row) { ctxMenu.style.display = 'none'; return; }
    e.preventDefault();
    ctxThreadId = row.dataset.threadId;
    ctxMenu.style.display = 'block';
    var menuW = ctxMenu.offsetWidth || 160;
    var menuH = ctxMenu.offsetHeight || 70;
    ctxMenu.style.left = Math.min(e.clientX, window.innerWidth - menuW - 4) + 'px';
    ctxMenu.style.top = Math.min(e.clientY, window.innerHeight - menuH - 4) + 'px';
  });

  document.addEventListener('click', function () { ctxMenu.style.display = 'none'; });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') ctxMenu.style.display = 'none';
  });

  document.getElementById('ctx-open').addEventListener('click', function () {
    if (!ctxThreadId) return;
    window.open('https://mail.google.com/mail/u/0/#inbox/' + ctxThreadId, '_blank');
    ctxMenu.style.display = 'none';
  });

  document.getElementById('ctx-trash').addEventListener('click', function () {
    ctxMenu.style.display = 'none';
    document.getElementById('trash-error').style.display = 'none';
    document.getElementById('trash-error').textContent = '';
    document.getElementById('trashModal').classList.add('active');
  });

  window.closeTrashModal = function () {
    document.getElementById('trashModal').classList.remove('active');
  };

  window.confirmTrash = function () {
    var btn = document.getElementById('trash-confirm-btn');
    btn.disabled = true;
    btn.textContent = 'Moving…';
    fetch('/gmail/thread/' + ctxThreadId + '/trash', {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    }).then(function (r) {
      if (r.ok) {
        closeTrashModal();
        var inboxRow = document.querySelector('tr[data-thread-id="' + ctxThreadId + '"]');
        var expandRow = document.getElementById('expand-' + ctxThreadId);
        if (inboxRow) inboxRow.remove();
        if (expandRow) expandRow.remove();
      } else {
        return r.json().then(function (data) {
          var errDiv = document.getElementById('trash-error');
          errDiv.textContent = data.error || 'Failed to move to Trash.';
          errDiv.style.display = 'block';
        });
      }
    }).catch(function () {
      var errDiv = document.getElementById('trash-error');
      errDiv.textContent = 'Request failed.';
      errDiv.style.display = 'block';
    }).finally(function () {
      btn.disabled = false;
      btn.textContent = 'Move to Trash';
    });
  };
}());

// ── Bank dropdown ─────────────────────────────────────────────────
(function () {
  function shortForBankId(id) {
    for (var i = 0; i < LABELS.length; i++) {
      if (LABELS[i].id === id) return LABELS[i].short;
    }
    return '—';
  }

  document.querySelectorAll('.bank-cell').forEach(function (cell) {
    cell.addEventListener('click', function (e) {
      e.stopPropagation();
      if (cell.querySelector('select') || !LABELS.length) return;

      var prevId = cell.dataset.bankId || '';
      var select = document.createElement('select');
      select.style.cssText = 'width:100%;border:none;background:transparent;'
        + 'font:inherit;font-weight:500;font-size:0.8rem;padding:0';

      var blank = document.createElement('option');
      blank.value = '';
      blank.textContent = '— select —';
      select.appendChild(blank);

      LABELS.forEach(function (parent) {
        var o = document.createElement('option');
        o.value = parent.id;
        o.textContent = parent.short;
        if (parent.id === prevId) o.selected = true;
        select.appendChild(o);
      });

      cell.textContent = '';
      cell.appendChild(select);
      select.focus();

      select.addEventListener('change', function () {
        var bankId = select.value;
        cell.removeChild(select);
        cell.textContent = '…';
        fetch('/gmail/thread/' + cell.dataset.threadId + '/bank', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ bank_id: bankId })
        }).then(function (r) {
          if (r.ok) {
            cell.textContent = bankId ? shortForBankId(bankId) : '—';
            cell.dataset.bankId = bankId;
            var row = cell.closest('.inbox-row');
            var subCell = row && row.querySelector('.sublabel-cell');
            if (subCell) { subCell.textContent = '—'; subCell.dataset.sublabelId = ''; }
            var fileBtn = row && row.querySelector('.file-btn');
            if (fileBtn) fileBtn.style.display = 'none';
          } else {
            cell.textContent = prevId ? shortForBankId(prevId) : '—';
          }
        }).catch(function () {
          cell.textContent = prevId ? shortForBankId(prevId) : '—';
        });
      });

      select.addEventListener('blur', function () {
        if (cell.querySelector('select')) {
          cell.removeChild(select);
          cell.textContent = prevId ? shortForBankId(prevId) : '—';
        }
      });

      select.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          cell.removeChild(select);
          cell.textContent = prevId ? shortForBankId(prevId) : '—';
        }
      });
    });
  });
}());

// ── Sub-label dropdown ────────────────────────────────────────────
(function () {
  function childrenForBankId(bankId) {
    for (var i = 0; i < LABELS.length; i++) {
      if (LABELS[i].id === bankId) return LABELS[i].children;
    }
    return [];
  }

  function shortForSublabelId(bankId, sublabelId) {
    var children = childrenForBankId(bankId);
    for (var i = 0; i < children.length; i++) {
      if (children[i].id === sublabelId) return children[i].short;
    }
    return '—';
  }

  document.querySelectorAll('.sublabel-cell').forEach(function (cell) {
    cell.addEventListener('click', function (e) {
      e.stopPropagation();
      if (cell.querySelector('select')) return;

      var row = cell.closest('.inbox-row');
      var bankCell = row && row.querySelector('.bank-cell');
      var bankId = bankCell ? bankCell.dataset.bankId : '';
      if (!bankId) return;

      var children = childrenForBankId(bankId);
      if (!children.length) return;

      var prevId = cell.dataset.sublabelId || '';
      var select = document.createElement('select');
      select.style.cssText = 'width:100%;border:none;background:transparent;'
        + 'font:inherit;font-size:0.8rem;padding:0';

      var blank = document.createElement('option');
      blank.value = '';
      blank.textContent = '— select —';
      select.appendChild(blank);

      children.forEach(function (child) {
        var o = document.createElement('option');
        o.value = child.id;
        o.textContent = child.short;
        if (child.id === prevId) o.selected = true;
        select.appendChild(o);
      });

      cell.textContent = '';
      cell.appendChild(select);
      select.focus();

      select.addEventListener('change', function () {
        var sublabelId = select.value;
        cell.removeChild(select);
        cell.textContent = '…';
        fetch('/gmail/thread/' + cell.dataset.threadId + '/sublabel', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
          body: JSON.stringify({ sublabel_id: sublabelId })
        }).then(function (r) {
          if (r.ok) {
            cell.textContent = sublabelId ? shortForSublabelId(bankId, sublabelId) : '—';
            cell.dataset.sublabelId = sublabelId;
            var fileBtn = row && row.querySelector('.file-btn');
            if (fileBtn) fileBtn.style.display = sublabelId ? '' : 'none';
          } else {
            cell.textContent = prevId ? shortForSublabelId(bankId, prevId) : '—';
          }
        }).catch(function () {
          cell.textContent = prevId ? shortForSublabelId(bankId, prevId) : '—';
        });
      });

      select.addEventListener('blur', function () {
        if (cell.querySelector('select')) {
          cell.removeChild(select);
          cell.textContent = prevId ? shortForSublabelId(bankId, prevId) : '—';
        }
      });

      select.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
          cell.removeChild(select);
          cell.textContent = prevId ? shortForSublabelId(bankId, prevId) : '—';
        }
      });
    });
  });
}());

// ── File button ───────────────────────────────────────────────────
(function () {
  document.querySelectorAll('.file-btn').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var threadId = btn.dataset.threadId;
      btn.disabled = true;
      btn.textContent = '…';
      fetch('/gmail/thread/' + threadId + '/file', {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      }).then(function (r) {
        if (r.ok || r.status === 404) {
          var inboxRow = document.querySelector('tr[data-thread-id="' + threadId + '"]');
          var expandRow = document.getElementById('expand-' + threadId);
          if (inboxRow) inboxRow.remove();
          if (expandRow) expandRow.remove();
        } else {
          btn.disabled = false;
          btn.textContent = '→';
          btn.style.color = 'var(--danger,#dc3545)';
          setTimeout(function () { btn.style.color = ''; }, 1500);
        }
      }).catch(function () {
        btn.disabled = false;
        btn.textContent = '→';
        btn.style.color = 'var(--danger,#dc3545)';
        setTimeout(function () { btn.style.color = ''; }, 1500);
      });
    });
  });
}());
</script>
{% endblock %}
```

- [ ] **Step 2: Run the test suite to verify no regressions**

```
pytest tests/functional/test_gmail.py tests/functional/test_gmail_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Verify in browser**

Visit `http://192.168.100.79:5001/gmail/inbox` as superuser and confirm:

- BANK column shows short names from real Gmail labels (e.g. "SHK") or "—"
- Clicking Bank cell opens a dropdown of "Alvin -" parent labels (short names)
- Selecting a bank: PATCHes, cell shows new label, Sub-label cell resets to "—", File button hidden
- Sub-label column shows "—" by default
- Clicking Sub-label with no Bank: nothing happens
- Clicking Sub-label with Bank set: dropdown of children for that bank
- Selecting sub-label: PATCHes, cell shows child short name, File "→" button appears
- Clicking "→": archives thread in Gmail, row disappears
- Escape in either dropdown: cancels, restores previous value
- Right-click context menu still works (Open in Gmail, Move to Trash)
- Thread expand still works when clicking From/Subject/Date cells
- At tablet width (≤1024px): Bank + Sub-label + From + Subject + Date visible; File + Snippet hidden

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/gmail/pages/gmail/inbox.html
git commit -m "Add Bank dropdown, Sub-label column, and File button to Gmail inbox"
```
