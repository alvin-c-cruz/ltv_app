import os
import base64
import re

from flask import current_app
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

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


def _token_path():
    return os.path.join(current_app.instance_path, 'gmail_token.json')


def _get_service():
    path = _token_path()
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    try:
        creds = Credentials.from_authorized_user_file(path, SCOPES)
    except (ValueError, KeyError) as e:
        raise ValueError(f'Invalid token file: {e}')
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(path, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def _header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def _extract_body(payload):
    mime = payload.get('mimeType', '')
    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    elif mime == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            html = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            return re.sub(r'<[^>]+>', ' ', html)
    for part in payload.get('parts', []):
        body = _extract_body(part)
        if body:
            return body
    return ''


def list_threads(max_results=20):
    """Return list of thread summaries (id, sender, subject, date, snippet)."""
    service = _get_service()
    result = service.users().threads().list(
        userId='me', maxResults=max_results
    ).execute()
    summaries = []
    for t in result.get('threads', []):
        thread = service.users().threads().get(
            userId='me', id=t['id'], format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()
        msgs = thread.get('messages', [])
        if not msgs:
            continue
        hdrs = msgs[0].get('payload', {}).get('headers', [])
        summaries.append({
            'id': t['id'],
            'sender': _header(hdrs, 'From'),
            'subject': _header(hdrs, 'Subject'),
            'date': _header(hdrs, 'Date'),
            'snippet': thread.get('snippet', ''),
        })
    return summaries


def get_thread(thread_id):
    """Return list of messages in a thread (sender, date, body)."""
    service = _get_service()
    thread = service.users().threads().get(
        userId='me', id=thread_id, format='full'
    ).execute()
    messages = []
    for msg in thread.get('messages', []):
        payload = msg.get('payload', {})
        hdrs = payload.get('headers', [])
        messages.append({
            'sender': _header(hdrs, 'From'),
            'date': _header(hdrs, 'Date'),
            'body': _extract_body(payload),
        })
    return messages


def trash_thread(thread_id):
    """Move a thread to Gmail Trash."""
    service = _get_service()
    service.users().threads().trash(userId='me', id=thread_id).execute()
