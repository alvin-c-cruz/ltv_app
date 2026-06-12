from flask import Blueprint, render_template, jsonify, flash
from flask_login import login_required
from googleapiclient.errors import HttpError

from ..auth import superuser_required
from .extensions.gmail_client import list_threads, get_thread

bp = Blueprint('gmail', __name__, template_folder='pages', url_prefix='/gmail')


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
