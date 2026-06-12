import pytest
from unittest.mock import patch, MagicMock, mock_open
import json


# ── _extract_body ────────────────────────────────────────────────────────────

def test_extract_body_plain_text():
    import base64
    from ltv_app.blueprints.gmail.extensions.gmail_client import _extract_body
    text = 'Hello world'
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    payload = {'mimeType': 'text/plain', 'body': {'data': encoded}, 'parts': []}
    assert _extract_body(payload) == 'Hello world'


def test_extract_body_html_strips_tags():
    import base64
    from ltv_app.blueprints.gmail.extensions.gmail_client import _extract_body
    html = '<p>Hello <b>world</b></p>'
    encoded = base64.urlsafe_b64encode(html.encode()).decode()
    payload = {'mimeType': 'text/html', 'body': {'data': encoded}, 'parts': []}
    result = _extract_body(payload)
    assert 'Hello' in result
    assert '<p>' not in result


def test_extract_body_empty_returns_empty_string():
    from ltv_app.blueprints.gmail.extensions.gmail_client import _extract_body
    payload = {'mimeType': 'text/plain', 'body': {}, 'parts': []}
    assert _extract_body(payload) == ''


def test_extract_body_multipart_finds_plain():
    import base64
    from ltv_app.blueprints.gmail.extensions.gmail_client import _extract_body
    text = 'Plain part'
    encoded = base64.urlsafe_b64encode(text.encode()).decode()
    payload = {
        'mimeType': 'multipart/mixed',
        'body': {},
        'parts': [
            {'mimeType': 'text/plain', 'body': {'data': encoded}, 'parts': []},
        ]
    }
    assert _extract_body(payload) == 'Plain part'


# ── _header ──────────────────────────────────────────────────────────────────

def test_header_found():
    from ltv_app.blueprints.gmail.extensions.gmail_client import _header
    headers = [{'name': 'From', 'value': 'alice@example.com'}]
    assert _header(headers, 'From') == 'alice@example.com'


def test_header_case_insensitive():
    from ltv_app.blueprints.gmail.extensions.gmail_client import _header
    headers = [{'name': 'from', 'value': 'alice@example.com'}]
    assert _header(headers, 'From') == 'alice@example.com'


def test_header_missing_returns_empty():
    from ltv_app.blueprints.gmail.extensions.gmail_client import _header
    assert _header([], 'Subject') == ''


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
