from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ltv2.extensions import db
from ltv2.models.transaction_type import TransactionType
from ltv2.blueprints.transaction_types.forms import TransactionTypeForm

bp = Blueprint("transaction_types", __name__, url_prefix="/transaction-types")


@bp.route("/")
@login_required
def list_types():
    show = request.args.get("show", "active")
    q = TransactionType.query if show == "all" else TransactionType.query_active()
    rows = q.order_by(TransactionType.priority, TransactionType.name).all()
    return render_template("transaction_types/list.html", rows=rows, show=show)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_type():
    form = TransactionTypeForm()
    if form.validate_on_submit():
        if TransactionType.query.filter_by(name=form.name.data).first():
            flash(f"Transaction type {form.name.data!r} already exists", "error")
            return redirect(url_for("transaction_types.add_type"))
        t = TransactionType(name=form.name.data,
                            behavior_category=form.behavior_category.data,
                            priority=form.priority.data if form.priority.data is not None else 0)
        db.session.add(t); db.session.commit()
        flash("Transaction type added", "success")
        return redirect(url_for("transaction_types.list_types"))
    return render_template("transaction_types/form.html", form=form, mode="add")


@bp.route("/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def edit_type(tid):
    t = db.get_or_404(TransactionType, tid)
    form = TransactionTypeForm(obj=t)
    if form.validate_on_submit():
        existing = TransactionType.query.filter_by(name=form.name.data).first()
        if existing and existing.id != t.id:
            flash(f"Transaction type {form.name.data!r} already exists", "error")
            return redirect(url_for("transaction_types.edit_type", tid=tid))
        t.name = form.name.data
        t.behavior_category = form.behavior_category.data
        t.priority = form.priority.data if form.priority.data is not None else 0
        db.session.commit()
        flash("Transaction type updated", "success")
        return redirect(url_for("transaction_types.list_types"))
    return render_template("transaction_types/form.html", form=form, mode="edit")


@bp.route("/<int:tid>/toggle-active", methods=["POST"])
@login_required
def toggle_active(tid):
    t = db.get_or_404(TransactionType, tid)
    t.is_active = not t.is_active
    db.session.commit()
    flash("Status updated", "success")
    return redirect(url_for("transaction_types.list_types", show=request.form.get("show", "active")))
