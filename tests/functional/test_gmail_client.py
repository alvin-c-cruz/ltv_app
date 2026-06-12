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
