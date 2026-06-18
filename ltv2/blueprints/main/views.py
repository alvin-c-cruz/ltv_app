from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


@bp.route("/")
def index():
    return render_template("index.html")
