from flask import Blueprint, render_template, flash, redirect, url_for, send_file

from .. auth import login_required
from .. database import get_db

from .forms import DateForm
from .extensions import get_transactions, CreateNotebook

bp = Blueprint('notebook', __name__, template_folder="pages", url_prefix="/notebook")


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    date_form = DateForm()

    trade_date = str(date_form.trade_date.data)[:10]

    context = {
        "date_form": date_form,
        "trade_date": trade_date
    }

    return render_template("notebook/home.html", **context)


@bp.route("/generate/<trade_date>")
@login_required
def generate(trade_date):
    db = get_db()
    transactions = get_transactions(db=db, trade_date=trade_date)
    notebook = CreateNotebook(db=db, trade_date=trade_date, transactions=transactions)

    return send_file('{}'.format(notebook.filename), as_attachment=True)
