from flask import Blueprint, flash, render_template

from ..auth import login_required
from ..database import get_db
from ...tz import ph_now
from ...workbook_download import send_workbook

from .edition import build_edition
from .extensions import EditionWorkbook
from .forms import EditionForm
from .price_set import read_price_set

bp = Blueprint("blocked_unblocked", __name__, template_folder="pages", url_prefix="/blocked-unblocked")


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    form = EditionForm()
    if form.validate_on_submit():
        db = get_db()
        as_of = form.report_date.data.strftime("%Y-%m-%d")
        upload = form.price_file.data
        csv_bytes = upload.read() if upload and getattr(upload, "filename", "") else None
        text = form.price_text.data or ""

        price_set = read_price_set(db, csv_bytes, text) if (csv_bytes or text.strip()) else None
        if price_set and price_set.skipped:
            flash("Not read from the price set: " + "; ".join(price_set.skipped), category="error")
        edition = build_edition(db, as_of, prices=price_set.prices if price_set else None,
                                price_label=f"prices supplied {ph_now():%d %b %Y %H:%M}")
        if edition.unpriced:
            flash("No price for " + ", ".join(edition.unpriced) + "; their market value is left blank.",
                  category="error")
        workbook = EditionWorkbook(edition)
        return send_workbook(workbook.output, workbook.download_name)

    return render_template("blocked_unblocked/home.html", form=form)
