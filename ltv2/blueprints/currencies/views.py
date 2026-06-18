from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.blueprints.currencies.forms import CurrencyForm

bp = Blueprint("currencies", __name__, url_prefix="/currencies")


@bp.route("/")
@login_required
def list_currencies():
    show = request.args.get("show", "active")
    q = Currency.query if show == "all" else Currency.query_active()
    rows = q.order_by(Currency.priority, Currency.code).all()
    return render_template("currencies/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_currency():
    form = CurrencyForm()
    if form.validate_on_submit():
        if Currency.query.filter_by(code=form.code.data).first():
            flash(f"Currency {form.code.data!r} already exists", "error")
            return redirect(url_for("currencies.add_currency"))
        c = Currency(code=form.code.data, name=form.name.data,
                     priority=form.priority.data if form.priority.data is not None else 0)
        db.session.add(c)
        db.session.commit()
        flash("Currency added", "success")
        return redirect(url_for("currencies.list_currencies"))
    return render_template("currencies/form.html", form=form, mode="add")


@bp.route("/<int:cid>/edit", methods=["GET", "POST"])
@login_required
def edit_currency(cid):
    c = db.get_or_404(Currency, cid)
    form = CurrencyForm(obj=c)
    if form.validate_on_submit():
        existing = Currency.query.filter_by(code=form.code.data).first()
        if existing and existing.id != c.id:
            flash(f"Currency {form.code.data!r} already exists", "error")
            return redirect(url_for("currencies.edit_currency", cid=cid))
        c.code = form.code.data
        c.name = form.name.data
        c.priority = form.priority.data if form.priority.data is not None else 0
        db.session.commit()
        flash("Currency updated", "success")
        return redirect(url_for("currencies.list_currencies"))
    return render_template("currencies/form.html", form=form, mode="edit")


@bp.route("/<int:cid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(cid):
    c = db.get_or_404(Currency, cid)
    c.is_active = not c.is_active
    db.session.commit()
    flash("Status updated", "success")
    # Read show from POST body, not query string
    show = request.form.get("show", "active")
    return redirect(url_for("currencies.list_currencies", show=show))
