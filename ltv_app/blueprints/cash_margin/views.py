from flask import Blueprint, send_file, current_app

from ..auth import login_required
from ..database import get_db
from ...tz import ph_today

bp = Blueprint('cash_margin', __name__, template_folder='pages', url_prefix='/cash-margin')


@bp.route('/download/<ccy>/<observation_month>')
@login_required
def download(ccy, observation_month):
    """observation_month is 'YYYY-MM' — matches legacy's forecast/cash_margin form field."""
    db = get_db()
    filename = build_cash_margin_file(db, ccy, observation_month, current_app.instance_path)
    return send_file(filename, as_attachment=True)
