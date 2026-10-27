from flask import Blueprint, render_template, flash, redirect, url_for

from .. auth import login_required
from .. database import get_db
from ...workbook_download import send_workbook

from .forms import DateForm
from .extensions import get_transactions, get_transfers, CreateNotebook

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
    transfers    = get_transfers(db=db, trade_date=trade_date)
    notebook = CreateNotebook(
        db=db, trade_date=trade_date,
        transactions=transactions, transfers=transfers
    )

    return send_workbook(notebook.output, notebook.download_name)
