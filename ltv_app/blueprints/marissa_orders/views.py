from flask import Blueprint, render_template, request, send_file

from ..auth import login_required
from ..database import get_db
from ...tz import ph_now

bp = Blueprint('marissa_orders', __name__, template_folder='pages', url_prefix='/maris')

_MONTHS = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
]


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    from .extensions import download_posting, download_daily_transactions, download_transaction_range

    db = get_db()
    trade_date = ph_now()
    month = trade_date.month - 1 if trade_date.month != 1 else 12
    year = trade_date.year
    years = range(2017, year + 1)

    if request.method == 'POST':
        cmd_button = request.form['cmd_button']
        if cmd_button == "Download Stock Posting":
            path = download_posting(db, int(request.form['posting_month']), int(request.form['posting_year']))
            return send_file(path, as_attachment=True)
        elif cmd_button == "Download Daily Transaction":
            path = download_daily_transactions(db, request.form['trade_date'])
            return send_file(path, as_attachment=True)
        elif cmd_button == "Download Transaction Range":
            path = download_transaction_range(db, request.form['range_start'], request.form['range_end'])
            return send_file(path, as_attachment=True)

    return render_template(
        'marissa_orders/home.html',
        months=_MONTHS, years=years, def_month=month, def_year=year, trade_date=trade_date
    )
