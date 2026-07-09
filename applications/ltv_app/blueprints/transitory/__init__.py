from flask import Blueprint, flash, redirect
import requests
from .. auth import login_required


bp = Blueprint('transitory', __name__, url_prefix='/transitory')


@bp.route("/unconfirmed")
@login_required
def unconfirmed():
    requests.get("http://127.0.0.1:9000/api/unconfirmed")

    flash("List of no charges is being generated.")
    return redirect("/")


@bp.route("/stock_position")
@login_required
def stock_position():
    # TODO: Create form
    requests.get("http://127.0.0.1:9000/api/stock_position")

    flash("Stock position is being generated.")
    return redirect("/")


