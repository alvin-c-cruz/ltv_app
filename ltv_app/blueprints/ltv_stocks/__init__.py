from flask import Blueprint, redirect, flash
import requests
from .. auth import login_required

bp = Blueprint("ltv_stocks", __name__, url_prefix="/ltv_stocks")


@bp.route("/")
@login_required
def home():
    requests.get("http://127.0.0.1:9000/api/ltv_stocks")

    flash("LTV Stocks is being generated.")
    return redirect("/")
