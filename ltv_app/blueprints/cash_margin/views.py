from flask import Blueprint, render_template, request, redirect, url_for, send_file, current_app

from ..auth import login_required
from ..database import get_db
from .extensions import build_cash_margin_file

bp = Blueprint('cash_margin', __name__, template_folder='pages', url_prefix='/cash-margin')


@bp.route('/', methods=['GET'])
@login_required
def home():
    """Simple form page so this report is reachable without hand-typing the
    download URL. GET with both query args present redirects straight to the
    existing download route (keeps that route's URL/behavior untouched);
    otherwise renders the form."""
    if 'ccy' in request.args and 'observation_month' in request.args:
        return redirect(url_for(
            'cash_margin.download',
            ccy=request.args['ccy'],
            observation_month=request.args['observation_month'],
        ))

    db = get_db()
    currencies = [
        row['ccy_id'] for row in
        db.execute("SELECT DISTINCT ccy_id FROM tbl_currency ORDER BY priority").fetchall()
    ]
    return render_template('cash_margin/home.html', currencies=currencies)


@bp.route('/download/<ccy>/<observation_month>')
@login_required
def download(ccy, observation_month):
    """observation_month is 'YYYY-MM' — matches legacy's forecast/cash_margin form field."""
    db = get_db()
    filename = build_cash_margin_file(db, ccy, observation_month, current_app.instance_path)
    return send_file(filename, as_attachment=True)
