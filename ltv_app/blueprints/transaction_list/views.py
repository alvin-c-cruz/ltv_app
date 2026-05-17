from flask import Blueprint, render_template, request, redirect, url_for, flash

from .. transactions import Transaction, TransactionShort
from .. auth import login_required

bp = Blueprint('transaction_list', __name__, template_folder='pages', url_prefix='/transaction-list')


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    rows_long = Transaction.query.all()
    
    context = {
        "rows_long": rows_long,
    }
    return render_template("transaction_list/home.html", **context)
