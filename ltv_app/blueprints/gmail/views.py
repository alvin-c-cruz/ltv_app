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
