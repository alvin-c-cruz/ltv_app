# Gmail Inbox — Trash & Open in Gmail Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-click context menu to the Gmail inbox admin page with two actions: "Open in Gmail" (new tab) and "Move to Trash" (with confirmation modal, API call, row removed from DOM on success).

**Architecture:** Backend gets a new `POST /gmail/thread/<id>/trash` route calling a new `trash_thread()` client function. Frontend adds a vanilla JS context menu and confirmation modal to the existing inbox template. All changes follow the existing patterns in `views.py`, `gmail_client.py`, and the fixings modal CSS.

**Tech Stack:** Python/Flask, Gmail API (`users().threads().trash()`), vanilla JS, existing modal CSS classes (`.modal-overlay`, `.modal`, `.modal-header`).

---

### Task 1: Backend — `trash_thread()` + route (TDD)

**Files:**
- Modify: `ltv_app/blueprints/gmail/extensions/gmail_client.py`
- Modify: `ltv_app/blueprints/gmail/views.py`
- Test: `tests/functional/test_gmail.py`

- [ ] **Step 1: Write the five failing tests**

Append to `tests/functional/test_gmail.py`:

```python
# ── POST /gmail/thread/<id>/trash ────────────────────────────────────────────

def test_trash_thread_success(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.trash_thread') as mock_trash:
        response = superuser_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 200
    mock_trash.assert_called_once_with('abc123')


def test_trash_thread_not_found(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=404), content=b'not found')
    with patch('ltv_app.blueprints.gmail.views.trash_thread', side_effect=err):
        response = superuser_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 404
    assert response.get_json()['error'] == 'Thread not found'


def test_trash_thread_not_configured(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.trash_thread',
               side_effect=FileNotFoundError):
        response = superuser_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 503
    assert response.get_json()['error'] == 'Gmail not configured'


def test_trash_thread_requires_superuser(auth_client):
    response = auth_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 403


def test_trash_thread_get_not_allowed(superuser_client):
    response = superuser_client.get('/gmail/thread/abc123/trash')
    assert response.status_code == 405
```

- [ ] **Step 2: Run tests to confirm they all fail**

```
pytest tests/functional/test_gmail.py::test_trash_thread_success tests/functional/test_gmail.py::test_trash_thread_not_found tests/functional/test_gmail.py::test_trash_thread_not_configured tests/functional/test_gmail.py::test_trash_thread_requires_superuser tests/functional/test_gmail.py::test_trash_thread_get_not_allowed -v
```

Expected: all 5 FAIL (404 — route not found).

- [ ] **Step 3: Add `trash_thread()` to `gmail_client.py`**

Append to the end of `ltv_app/blueprints/gmail/extensions/gmail_client.py`:

```python
def trash_thread(thread_id):
    """Move a thread to Gmail Trash."""
    service = _get_service()
    service.users().threads().trash(userId='me', id=thread_id).execute()
```

- [ ] **Step 4: Add the route to `views.py`**

Replace the import line at the top of `ltv_app/blueprints/gmail/views.py`:

```python
from .extensions.gmail_client import list_threads, get_thread, trash_thread
```

Append the new route after the existing `thread()` function:

```python
@bp.route('/thread/<thread_id>/trash', methods=['POST'])
@login_required
@superuser_required
def trash_thread_view(thread_id):
    try:
        trash_thread(thread_id)
    except (FileNotFoundError, ValueError):
        return jsonify({'error': 'Gmail not configured'}), 503
    except HttpError as e:
        if e.resp.status == 404:
            return jsonify({'error': 'Thread not found'}), 404
        return jsonify({'error': str(e)}), 500
    return jsonify({}), 200
```

- [ ] **Step 5: Run tests to confirm all 5 pass**

```
pytest tests/functional/test_gmail.py::test_trash_thread_success tests/functional/test_gmail.py::test_trash_thread_not_found tests/functional/test_gmail.py::test_trash_thread_not_configured tests/functional/test_gmail.py::test_trash_thread_requires_superuser tests/functional/test_gmail.py::test_trash_thread_get_not_allowed -v
```

Expected: all 5 PASS.

- [ ] **Step 6: Run the full test suite to check for regressions**

```
pytest tests/functional/test_gmail.py -v
```

Expected: all tests PASS (was 12, now 17).

- [ ] **Step 7: Commit**

```bash
git add ltv_app/blueprints/gmail/extensions/gmail_client.py ltv_app/blueprints/gmail/views.py tests/functional/test_gmail.py
git commit -m "Add trash_thread() and POST /gmail/thread/<id>/trash route"
```

---

### Task 2: Frontend — Right-click context menu, confirmation modal, JS

**Files:**
- Modify: `ltv_app/blueprints/gmail/pages/gmail/inbox.html`

- [ ] **Step 1: Add context menu HTML**

Inside the `{% elif threads is not none %}` block, just before the `<div class="table-wrap"...>` line, add:

```html
{# ── Right-click context menu ──────────────────────────────────── #}
<div id="ctx-menu" style="display:none;position:fixed;z-index:1000;background:#fff;
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
```

- [ ] **Step 2: Add confirmation modal HTML**

After the closing `</div>` of `div.table-wrap` (and still inside the `{% elif %}` block, before `{% endif %}`), add:

```html
{# ── Trash confirmation modal ──────────────────────────────────── #}
<div class="modal-overlay" id="trashModal"
     onclick="if(event.target===this)closeTrashModal()">
  <div class="modal">
    <div class="modal-header">
      <span class="modal-title">Move to Trash</span>
      <button type="button" class="modal-close"
              onclick="closeTrashModal()">&times;</button>
    </div>
    <div style="padding:1.25rem">
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
```

- [ ] **Step 3: Add JS for context menu and modal**

Inside the existing `<script>` block, after the closing `}());` of the IIFE (thread-expand JS) and before `</script>`, add:

```javascript
// ── Context menu ──────────────────────────────────────────────────
(function () {
  var ctxMenu = document.getElementById('ctx-menu');
  var ctxThreadId = null;

  document.addEventListener('contextmenu', function (e) {
    var row = e.target.closest('.inbox-row');
    if (!row) { ctxMenu.style.display = 'none'; return; }
    e.preventDefault();
    ctxThreadId = row.dataset.threadId;
    ctxMenu.style.display = 'block';
    ctxMenu.style.left = e.clientX + 'px';
    ctxMenu.style.top = e.clientY + 'px';
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

  // ── Trash modal ──────────────────────────────────────────────────
  window.closeTrashModal = function () {
    document.getElementById('trashModal').classList.remove('active');
  };

  window.confirmTrash = function () {
    var btn = document.getElementById('trash-confirm-btn');
    btn.disabled = true;
    btn.textContent = 'Moving…';

    fetch('/gmail/thread/' + ctxThreadId + '/trash', { method: 'POST' })
      .then(function (r) {
        if (r.ok) {
          closeTrashModal();
          var inboxRow = document.querySelector('[data-thread-id="' + ctxThreadId + '"]');
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
      })
      .catch(function () {
        var errDiv = document.getElementById('trash-error');
        errDiv.textContent = 'Request failed.';
        errDiv.style.display = 'block';
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = 'Move to Trash';
      });
  };
}());
```

- [ ] **Step 4: Verify in browser**

Visit `http://192.168.100.79:5001/gmail/inbox` as a superuser.

Check these behaviours manually:
- Right-clicking a row shows the context menu with two items
- Clicking anywhere else dismisses the menu
- "Open in Gmail" opens a new tab at the correct Gmail thread URL
- "Move to Trash" shows the confirmation modal
- Cancel closes the modal without any change
- Confirm moves the thread to Trash and removes the row from the page

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/gmail/pages/gmail/inbox.html
git commit -m "Add right-click context menu with Open in Gmail and Move to Trash actions"
```
