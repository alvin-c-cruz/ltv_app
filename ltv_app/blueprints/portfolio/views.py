from flask import Blueprint, render_template, flash, current_app, send_file
import os

from .. database import get_db
from .. auth import login_required

from .forms import Form
from .extensions import CreateExcel

bp = Blueprint('portfolio', __name__, template_folder="pages", url_prefix="/portfolio")


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    form = Form()

    if form.validate_on_submit():
        report_date = form.report_date.data.strftime("%Y-%m-%d")
        excel_file = CreateExcel(
            path=os.path.join(current_app.instance_path, "temp"),
            report_date=report_date,
            db=get_db()
        )
        return send_file(excel_file.filename, as_attachment=True)

    context = {
        "form": form,
    }
    return render_template("portfolio/home.html", **context)
