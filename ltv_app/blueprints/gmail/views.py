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
