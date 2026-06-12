# Gmail Inbox — Bank Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a BANK column as the first column in the Gmail inbox table, auto-guessed from sender domain, editable inline, and persisted to SQLite.

**Architecture:** `guess_bank()` is a pure function in `gmail_client.py`. DB reads/writes (stored overrides) live in `views.py` with two helpers: `_ensure_bank_table()` and `_get_stored_banks()`. The inbox view merges stored labels with domain guesses. A new `PATCH /gmail/thread/<id>/bank` route saves overrides. The frontend adds a `bank-cell` td with vanilla JS inline editing.

**Tech Stack:** Python/Flask, SQLite (`get_db()`), vanilla JS, existing inbox template.

---

### Task 1: `guess_bank()` function (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/extensions/gmail_client.py`
- Test: `tests/functional/test_gmail_client.py`

- [ ] **Step 1: Write 5 failing unit tests**

Append to `tests/functional/test_gmail_client.py`:

```python
# ── guess_bank ───────────────────────────────────────────────────────────────

def test_guess_bank_ebshk():
    from ltv_app.blueprints.gmail.extensions.gmail_client import guess_bank
    assert guess_bank('Cindy Lam <Cindy.Lam@ebshk.com>') == 'SHK'


def test_guess_bank_db():
    from ltv_app.blueprints.gmail.extensions.gmail_client import guess_bank
    assert guess_bank('Roger Suen <roger.suen@db.com>') == 'DB'


def test_guess_bank_trident():
    from ltv_app.blueprints.gmail.extensions.gmail_client import guess_bank
    assert guess_bank('Wesley Wong <wwong@tridenttrust.com>') == 'Trident'


def test_guess_bank_unknown():
    from ltv_app.blueprints.gmail.extensions.gmail_client import guess_bank
    assert guess_bank('Larry Villareal <larrylilia@gmail.com>') == '—'


def test_guess_bank_bare_email_format():
    from ltv_app.blueprints.gmail.extensions.gmail_client import guess_bank
    assert guess_bank('user@ebshk.com') == 'SHK'
```

- [ ] **Step 2: Run tests to confirm all 5 fail**

```
pytest tests/functional/test_gmail_client.py::test_guess_bank_ebshk tests/functional/test_gmail_client.py::test_guess_bank_db tests/functional/test_gmail_client.py::test_guess_bank_trident tests/functional/test_gmail_client.py::test_guess_bank_unknown tests/functional/test_gmail_client.py::test_guess_bank_bare_email_format -v
```

Expected: all 5 FAIL (ImportError or NameError — function not defined).

- [ ] **Step 3: Add `BANK_DOMAINS` dict and `guess_bank()` to `gmail_client.py`**

Add after the `SCOPES` constant at the top of `ltv_app/blueprints/gmail/extensions/gmail_client.py`:

```python
BANK_DOMAINS = {
    'ebshk.com': 'SHK',
    'db.com': 'DB',
    'tridenttrust.com': 'Trident',
}


def guess_bank(sender):
    """Return a short bank label guessed from the sender's email domain."""
    match = re.search(r'<[^>]*@([^>]+)>', sender)
    if match:
        domain = match.group(1).lower()
    elif '@' in sender:
        domain = sender.split('@')[-1].strip().lower()
    else:
        return '—'
    return BANK_DOMAINS.get(domain, '—')
```

`re` is already imported at the top of the file.

- [ ] **Step 4: Run tests to confirm all 5 pass**

```
pytest tests/functional/test_gmail_client.py::test_guess_bank_ebshk tests/functional/test_gmail_client.py::test_guess_bank_db tests/functional/test_gmail_client.py::test_guess_bank_trident tests/functional/test_gmail_client.py::test_guess_bank_unknown tests/functional/test_gmail_client.py::test_guess_bank_bare_email_format -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Run full client test suite to check for regressions**

```
pytest tests/functional/test_gmail_client.py -v
```

Expected: all 12 tests PASS (was 7, now 12).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/gmail/extensions/gmail_client.py tests/functional/test_gmail_client.py
git commit -m "Add guess_bank() with domain-to-bank mapping"
```

---

### Task 2: Backend — DB helpers + enhanced inbox() + PATCH bank route (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/views.py`
- Test: `tests/functional/test_gmail.py`

- [ ] **Step 1: Write 6 failing tests for the PATCH route**

Append to `tests/functional/test_gmail.py`:

```python
# ── PATCH /gmail/thread/<id>/bank ────────────────────────────────────────────

def test_bank_patch_success(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_label': 'SHK'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 200
    assert response.get_json() == {}


def test_bank_patch_clear(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_label': ''},
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
        json={'bank_label': 'SHK'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 403


def test_bank_patch_requires_xhr(superuser_client):
    response = superuser_client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_label': 'SHK'}
    )
    assert response.status_code == 403
    assert response.get_json()['error'] == 'Forbidden'


def test_bank_patch_unauthenticated(client):
    response = client.patch(
        '/gmail/thread/abc123/bank',
        json={'bank_label': 'SHK'},
        headers={'X-Requested-With': 'XMLHttpRequest'}
    )
    assert response.status_code == 302
    assert '/login' in response.headers['Location']
```

- [ ] **Step 2: Run tests to confirm all 6 fail**

```
pytest tests/functional/test_gmail.py::test_bank_patch_success tests/functional/test_gmail.py::test_bank_patch_clear tests/functional/test_gmail.py::test_bank_patch_missing_key tests/functional/test_gmail.py::test_bank_patch_requires_superuser tests/functional/test_gmail.py::test_bank_patch_requires_xhr tests/functional/test_gmail.py::test_bank_patch_unauthenticated -v
```

Expected: all 6 FAIL (404 — route not found).

- [ ] **Step 3: Rewrite `views.py` with DB helpers and new route**

Replace the entire content of `ltv_app/blueprints/gmail/views.py` with:

```python
from flask import Blueprint, render_template, jsonify, flash, request
from flask_login import login_required
from googleapiclient.errors import HttpError

from ..auth import superuser_required
from ..database import get_db
from .extensions.gmail_client import list_threads, get_thread, trash_thread, guess_bank

bp = Blueprint('gmail', __name__, template_folder='pages', url_prefix='/gmail')


def _ensure_bank_table(db):
    db.execute('''
        CREATE TABLE IF NOT EXISTS tbl_gmail_thread_bank (
            thread_id TEXT PRIMARY KEY,
            bank_label TEXT NOT NULL
        )
    ''')
    db.commit()


def _get_stored_banks(db, thread_ids):
    if not thread_ids:
        return {}
    placeholders = ','.join('?' * len(thread_ids))
    rows = db.execute(
        f'SELECT thread_id, bank_label FROM tbl_gmail_thread_bank WHERE thread_id IN ({placeholders})',
        thread_ids
    ).fetchall()
    return {row[0]: row[1] for row in rows}


@bp.route('/inbox')
@login_required
@superuser_required
def inbox():
    try:
        threads = list_threads(max_results=20)
    except (FileNotFoundError, ValueError):
        return render_template('gmail/inbox.html', threads=None, not_configured=True)
    except HttpError as e:
        flash(f'Gmail API error: {e}', 'danger')
        return render_template('gmail/inbox.html', threads=[], not_configured=False)
    db = get_db()
    _ensure_bank_table(db)
    stored = _get_stored_banks(db, [t['id'] for t in threads])
    for t in threads:
        t['bank'] = stored.get(t['id']) or guess_bank(t['sender'])
    return render_template('gmail/inbox.html', threads=threads, not_configured=False)


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
    if data is None or 'bank_label' not in data:
        return jsonify({'error': 'Missing bank_label'}), 400
    label = data['bank_label'].strip()
    db = get_db()
    _ensure_bank_table(db)
    if label:
        db.execute(
            'INSERT OR REPLACE INTO tbl_gmail_thread_bank (thread_id, bank_label) VALUES (?, ?)',
            (thread_id, label)
        )
    else:
        db.execute('DELETE FROM tbl_gmail_thread_bank WHERE thread_id = ?', (thread_id,))
    db.commit()
    return jsonify({}), 200
```

- [ ] **Step 4: Run the 6 new tests to confirm they pass**

```
pytest tests/functional/test_gmail.py::test_bank_patch_success tests/functional/test_gmail.py::test_bank_patch_clear tests/functional/test_gmail.py::test_bank_patch_missing_key tests/functional/test_gmail.py::test_bank_patch_requires_superuser tests/functional/test_gmail.py::test_bank_patch_requires_xhr tests/functional/test_gmail.py::test_bank_patch_unauthenticated -v
```

Expected: all 6 PASS.

- [ ] **Step 5: Run full Gmail test suite to check for regressions**

```
pytest tests/functional/test_gmail.py -v
```

Expected: all 26 tests PASS (was 20, now 26).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/gmail/views.py tests/functional/test_gmail.py
git commit -m "Add PATCH /gmail/thread/<id>/bank route and DB persistence for bank labels"
```

---

### Task 3: Frontend — BANK column, inline edit, responsive widths

**Files:**
- Modify: `ltv_app/blueprints/gmail/pages/gmail/inbox.html`

- [ ] **Step 1: Update responsive media query widths**

The BANK column is now first (nth-child 1). Snippet is still last-child and still hidden. Replace the existing `@media` block:

```css
@media (max-width: 1024px) {
  #inbox-table { table-layout: fixed; width: 100%; }
  #inbox-table th:last-child,
  #inbox-table td:last-child { display: none; }
  #inbox-table th:nth-child(1) { width: 8% !important; }
  #inbox-table th:nth-child(2) { width: 30% !important; }
  #inbox-table th:nth-child(3) { width: 42% !important; }
  #inbox-table th:nth-child(4) { width: 20% !important; }
  #inbox-table td { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
```

- [ ] **Step 2: Add BANK column header and update desktop widths**

Replace the existing `<thead>` block:

```html
    <thead>
      <tr>
        <th style="width:8%">Bank</th>
        <th style="width:24%">From</th>
        <th style="width:28%">Subject</th>
        <th style="width:12%">Date</th>
        <th style="width:28%">Snippet</th>
      </tr>
    </thead>
```

- [ ] **Step 3: Add `bank-cell` td as first cell in each inbox row**

Replace the existing `{% for thread in threads %}` row:

```html
    {% for thread in threads %}
      <tr class="inbox-row" data-thread-id="{{ thread.id }}" style="cursor:pointer">
        <td class="bank-cell" data-thread-id="{{ thread.id }}"
            style="font-weight:500;font-size:0.8rem;cursor:text">{{ thread.bank }}</td>
        <td>{{ thread.sender }}</td>
        <td>{{ thread.subject }}</td>
        <td>{{ thread.date }}</td>
        <td style="color:var(--text-muted);font-size:0.875rem">{{ thread.snippet }}</td>
      </tr>
```

- [ ] **Step 4: Add inline edit JS**

Inside the existing `<script>` block, after the context-menu IIFE closing `}());` and before `</script>`, add:

```javascript
// ── Bank cell inline edit ─────────────────────────────────────────
(function () {
  function flashRed(el) {
    el.style.color = 'var(--danger,#dc3545)';
    setTimeout(function () { el.style.color = ''; }, 1500);
  }

  document.querySelectorAll('.bank-cell').forEach(function (cell) {
    cell.addEventListener('click', function (e) {
      e.stopPropagation();
      if (cell.querySelector('input')) return;

      var prev = cell.textContent.trim();
      var input = document.createElement('input');
      input.value = prev === '—' ? '' : prev;
      input.style.cssText = 'width:100%;border:none;outline:none;background:transparent;'
        + 'font:inherit;font-weight:500;font-size:0.8rem;padding:0';
      cell.textContent = '';
      cell.appendChild(input);
      input.focus();
      input.select();

      function save() {
        if (!cell.querySelector('input')) return;
        var label = input.value.trim();
        if (label === (prev === '—' ? '' : prev)) {
          cell.textContent = prev;
          return;
        }
        input.disabled = true;
        input.style.opacity = '0.5';
        fetch('/gmail/thread/' + cell.dataset.threadId + '/bank', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ bank_label: label })
        })
          .then(function (r) {
            if (r.ok) {
              cell.textContent = label || '—';
            } else {
              cell.textContent = prev;
              flashRed(cell);
            }
          })
          .catch(function () {
            cell.textContent = prev;
            flashRed(cell);
          });
      }

      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); save(); }
        if (e.key === 'Escape') { cell.textContent = prev; }
      });
      input.addEventListener('blur', save);
    });
  });
}());
```

- [ ] **Step 5: Verify in browser**

Visit `http://192.168.100.79:5001/gmail/inbox` as a superuser.

Check:
- BANK column appears as first column with auto-guessed labels (SHK for ebshk.com, DB for db.com, etc.)
- Clicking a bank cell opens an inline input
- Typing a new label and pressing Enter saves it (PATCH fires, cell updates)
- Pressing Escape cancels without saving
- Clearing the value and saving resets to the domain guess (cell shows `—` or the guessed value)
- At tablet width (≤1024px): BANK, From, Subject, Date all visible — Snippet hidden
- Right-click context menu still works on rows
- Thread expand still works when clicking non-bank cells

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/gmail/pages/gmail/inbox.html
git commit -m "Add BANK column with inline edit to Gmail inbox"
```
