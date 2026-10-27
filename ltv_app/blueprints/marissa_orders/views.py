from flask import Blueprint, render_template, request, redirect, url_for, flash

from ..auth import login_required
from ..database import get_db
from ...form_fields import FormFields
from ...tz import ph_now
from ...workbook_download import send_workbook

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
            posted = FormFields(request.form)
            posting_month = posted.integer('posting_month', 'Month')
            posting_year = posted.integer('posting_year', 'Year')
            if posted.error:
                flash(posted.error)
                return redirect(url_for('marissa_orders.home'))
            return send_workbook(*download_posting(db, posting_month, posting_year))
        elif cmd_button == "Download Daily Transaction":
            return send_workbook(*download_daily_transactions(db, request.form['trade_date']))
        elif cmd_button == "Download Transaction Range":
            return send_workbook(*download_transaction_range(db, request.form['range_start'], request.form['range_end']))

    return render_template(
        'marissa_orders/home.html',
        months=_MONTHS, years=years, def_month=month, def_year=year, trade_date=trade_date
    )
