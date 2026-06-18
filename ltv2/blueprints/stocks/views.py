from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.stock import Stock
from ltv2.models.currency import Currency
from ltv2.blueprints.stocks.forms import StockForm

bp = Blueprint("stocks", __name__, url_prefix="/stocks")


def _currency_choices():
    return [(c.id, c.code) for c in Currency.query_active().order_by(Currency.code).all()]


@bp.route("/")
@login_required
def list_stocks():
    show = request.args.get("show", "active")
    q = Stock.query if show == "all" else Stock.query_active()
    rows = q.order_by(Stock.code).all()
    return render_template("stocks/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_stock():
    form = StockForm()
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        if Stock.query.filter_by(code=form.code.data).first():
            flash(f"Stock {form.code.data!r} already exists", "error")
            return redirect(url_for("stocks.add_stock"))
        s = Stock(code=form.code.data, company_name=form.company_name.data,
                  stock_name=form.stock_name.data, yahoo_ticker=form.yahoo_ticker.data,
                  security_code=form.security_code.data, currency_id=form.currency_id.data)
        db.session.add(s)
        db.session.commit()
        flash("Stock added", "success")
        return redirect(url_for("stocks.list_stocks"))
    return render_template("stocks/form.html", form=form, mode="add")


@bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit_stock(sid):
    s = db.get_or_404(Stock, sid)
    form = StockForm(obj=s)
    form.currency_id.choices = _currency_choices()
    if form.validate_on_submit():
        existing = Stock.query.filter_by(code=form.code.data).first()
        if existing and existing.id != s.id:
            flash(f"Stock {form.code.data!r} already exists", "error")
            return redirect(url_for("stocks.edit_stock", sid=sid))
        s.code = form.code.data
        s.company_name = form.company_name.data
        s.stock_name = form.stock_name.data
        s.yahoo_ticker = form.yahoo_ticker.data
        s.security_code = form.security_code.data
        s.currency_id = form.currency_id.data
        db.session.commit()
        flash("Stock updated", "success")
        return redirect(url_for("stocks.list_stocks"))
    return render_template("stocks/form.html", form=form, mode="edit")


@bp.route("/<int:sid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(sid):
    s = db.get_or_404(Stock, sid)
    s.is_active = not s.is_active
    db.session.commit()
    flash("Status updated", "success")
    show = request.form.get("show", "active")
    return redirect(url_for("stocks.list_stocks", show=show))
