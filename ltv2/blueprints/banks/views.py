from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.bank import Bank
from ltv2.blueprints.banks.forms import BankForm

bp = Blueprint("banks", __name__, url_prefix="/banks")


@bp.route("/")
@login_required
def list_banks():
    show = request.args.get("show", "active")
    q = Bank.query if show == "all" else Bank.query_active()
    rows = q.order_by(Bank.priority, Bank.bank_code).all()
    return render_template("banks/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_bank():
    form = BankForm()
    if form.validate_on_submit():
        if Bank.query.filter_by(bank_code=form.bank_code.data).first():
            flash(f"Bank {form.bank_code.data!r} already exists", "error")
            return redirect(url_for("banks.add_bank"))
        # Improvement 1: use explicit None check, not falsy coercion
        b = Bank(
            bank_code=form.bank_code.data,
            name=form.name.data,
            report_label=form.report_label.data,
            transaction_basis=form.transaction_basis.data,
            priority=form.priority.data if form.priority.data is not None else 0,
        )
        db.session.add(b)
        db.session.commit()
        flash("Bank added", "success")
        return redirect(url_for("banks.list_banks"))
    return render_template("banks/form.html", form=form, mode="add")


@bp.route("/<int:bid>/edit", methods=["GET", "POST"])
@login_required
def edit_bank(bid):
    b = db.get_or_404(Bank, bid)
    form = BankForm(obj=b)
    if form.validate_on_submit():
        existing = Bank.query.filter_by(bank_code=form.bank_code.data).first()
        if existing and existing.id != b.id:
            flash(f"Bank {form.bank_code.data!r} already exists", "error")
            return redirect(url_for("banks.edit_bank", bid=bid))
        b.bank_code = form.bank_code.data
        b.name = form.name.data
        b.report_label = form.report_label.data
        b.transaction_basis = form.transaction_basis.data
        # Improvement 1: use explicit None check, not falsy coercion
        b.priority = form.priority.data if form.priority.data is not None else 0
        db.session.commit()
        flash("Bank updated", "success")
        return redirect(url_for("banks.list_banks"))
    return render_template("banks/form.html", form=form, mode="edit")


@bp.route("/<int:bid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(bid):
    b = db.get_or_404(Bank, bid)
    b.is_active = not b.is_active
    db.session.commit()
    flash("Status updated", "success")
    # Improvement 3: read show from POST body, not query string
    show = request.form.get("show", "active")
    return redirect(url_for("banks.list_banks", show=show))
