from flask import Blueprint, current_app, g
import sqlite3

from .. auth import login_required
from ..bank import BankAccount
from ..currency import Currency
from ..stocks import Stocks

bp = Blueprint('database', __name__, url_prefix="/database")


@bp.route('/')
@login_required
def home():
    return "Database home"


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row

    return g.db


@bp.before_app_request
def base_variables():
    db = get_db()
    if "bank_accounts" not in g:
        g.bank_accounts = db.execute(
            "SELECT ref_num, bank_name, bank_id FROM tbl_bank_account "
            "WHERE is_active = 1 ORDER BY priority"
        ).fetchall()

    if "stocks" not in g:
        stocks = Stocks(db=db)
        g.stocks = stocks.all(fields=["ref_num", "code", "stock_name", "ccy_ref"], order_by=["code"])

    if "currencies" not in g:
        currencies = Currency(db=db)
        g.currencies = currencies.all(fields=["ref_num", "ccy_id"], order_by=["priority"])
