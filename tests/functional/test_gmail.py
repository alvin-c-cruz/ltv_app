import pytest
from unittest.mock import patch, MagicMock


THREADS = [
    {'id': 'thread1', 'sender': 'alice@example.com', 'subject': 'Hello',
     'date': 'Jun 1', 'snippet': 'Hi there'}
]
MESSAGES = [
    {'sender': 'alice@example.com', 'date': 'Jun 1', 'body': 'Hello body'}
]


# ── /gmail/inbox ─────────────────────────────────────────────────────────────

def test_inbox_unauthenticated_redirects(client):
    response = client.get('/gmail/inbox')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_inbox_non_superuser_gets_403(auth_client):
    response = auth_client.get('/gmail/inbox')
    assert response.status_code == 403


def test_inbox_superuser_token_missing_shows_not_configured(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.list_threads',
               side_effect=FileNotFoundError):
        response = superuser_client.get('/gmail/inbox')
    assert response.status_code == 200
    assert b'not configured' in response.data.lower()


def test_inbox_superuser_token_invalid_shows_not_configured(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.list_threads',
               side_effect=ValueError):
        response = superuser_client.get('/gmail/inbox')
    assert response.status_code == 200
    assert b'not configured' in response.data.lower()


def test_inbox_superuser_api_error_flashes_message(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=500), content=b'server error')
    with patch('ltv_app.blueprints.gmail.views.list_threads', side_effect=err):
        response = superuser_client.get('/gmail/inbox')
    assert response.status_code == 200
    assert b'Gmail API error' in response.data


def test_inbox_superuser_shows_threads(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.list_threads',
               return_value=THREADS):
        response = superuser_client.get('/gmail/inbox')
    assert response.status_code == 200
    assert b'alice@example.com' in response.data
    assert b'Hello' in response.data


# ── /gmail/thread/<id> ───────────────────────────────────────────────────────

def test_thread_unauthenticated_redirects(client):
    response = client.get('/gmail/thread/abc123')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_thread_non_superuser_gets_403(auth_client):
    response = auth_client.get('/gmail/thread/abc123')
    assert response.status_code == 403


def test_thread_returns_json_messages(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.get_thread',
               return_value=MESSAGES):
        response = superuser_client.get('/gmail/thread/abc123')
    assert response.status_code == 200
    data = response.get_json()
    assert data['messages'][0]['sender'] == 'alice@example.com'
    assert data['messages'][0]['body'] == 'Hello body'


def test_thread_not_found_returns_404(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=404), content=b'not found')
    with patch('ltv_app.blueprints.gmail.views.get_thread', side_effect=err):
        response = superuser_client.get('/gmail/thread/abc123')
    assert response.status_code == 404
    assert response.get_json()['error'] == 'Thread not found'


def test_thread_api_error_returns_500(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=500), content=b'server error')
    with patch('ltv_app.blueprints.gmail.views.get_thread', side_effect=err):
        response = superuser_client.get('/gmail/thread/abc123')
    assert response.status_code == 500
    assert 'error' in response.get_json()


def test_thread_not_configured_returns_503(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.get_thread',
               side_effect=FileNotFoundError):
        response = superuser_client.get('/gmail/thread/abc123')
    assert response.status_code == 503
    assert response.get_json()['error'] == 'Gmail not configured'


# ── POST /gmail/thread/<id>/trash ────────────────────────────────────────────

def test_trash_thread_success(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.trash_thread') as mock_trash:
        response = superuser_client.post('/gmail/thread/abc123/trash',
                                         headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    mock_trash.assert_called_once_with('abc123')


def test_trash_thread_not_found(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=404), content=b'not found')
    with patch('ltv_app.blueprints.gmail.views.trash_thread', side_effect=err):
        response = superuser_client.post('/gmail/thread/abc123/trash',
                                          headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 404
    assert response.get_json()['error'] == 'Thread not found'


def test_trash_thread_not_configured(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.trash_thread',
               side_effect=FileNotFoundError):
        response = superuser_client.post('/gmail/thread/abc123/trash',
                                          headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 503
    assert response.get_json()['error'] == 'Gmail not configured'


def test_trash_thread_requires_superuser(auth_client):
    response = auth_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 403


def test_trash_thread_get_not_allowed(superuser_client):
    response = superuser_client.get('/gmail/thread/abc123/trash')
    assert response.status_code == 405


def test_trash_thread_api_error_returns_500(superuser_client):
    from googleapiclient.errors import HttpError
    err = HttpError(resp=MagicMock(status=500), content=b'server error')
    with patch('ltv_app.blueprints.gmail.views.trash_thread', side_effect=err):
        response = superuser_client.post('/gmail/thread/abc123/trash',
                                          headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 500
    assert 'error' in response.get_json()


def test_trash_thread_unauthenticated_redirects(client):
    response = client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_trash_thread_requires_xhr_header(superuser_client):
    with patch('ltv_app.blueprints.gmail.views.trash_thread'):
        response = superuser_client.post('/gmail/thread/abc123/trash')
    assert response.status_code == 403
    assert response.get_json()['error'] == 'Forbidden'


# ── PATCH /gmail/thread/<id>/bank ───────────────────────────────────────────

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
