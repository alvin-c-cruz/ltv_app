from flask import Blueprint, render_template, flash

from .. database import get_db
from .. auth import login_required
from ...workbook_download import send_workbook

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
            report_date=report_date,
            db=get_db()
        )
        return send_workbook(excel_file.output, excel_file.download_name)

    context = {
        "form": form,
    }
    return render_template("portfolio/home.html", **context)
