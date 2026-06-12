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
