from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.holiday import Holiday
from ltv2.models.currency import Currency
from ltv2.blueprints.holidays.forms import HolidayForm

bp = Blueprint("holidays", __name__, url_prefix="/holidays")


def _currency_choices():
    return [(c.id, c.code) for c in Currency.query_active().order_by(Currency.code).all()]


@bp.route("/")
@login_required
def list_holidays():
    show = request.args.get("show", "active")
    q = Holiday.query if show == "all" else Holiday.query_active()
    rows = q.order_by(Holiday.holiday_date).all()
    return render_template("holidays/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_holiday():
    form = HolidayForm()
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        dup = Holiday.query.filter_by(currency_id=form.currency_id.data,
                                      holiday_date=form.holiday_date.data).first()
        if dup:
            flash("Holiday already exists for that currency and date", "error")
            return redirect(url_for("holidays.add_holiday"))
        h = Holiday(currency_id=form.currency_id.data, holiday_date=form.holiday_date.data)
        db.session.add(h)
        db.session.commit()
        flash("Holiday added", "success")
        return redirect(url_for("holidays.list_holidays"))
    return render_template("holidays/form.html", form=form)


@bp.route("/<int:hid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(hid):
    h = db.get_or_404(Holiday, hid)
    h.is_active = not h.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("holidays.list_holidays", show=request.form.get("show", "active")))
