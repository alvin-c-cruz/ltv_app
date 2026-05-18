from flask import Blueprint, render_template, redirect, url_for, flash, request

from .. auth import login_required
from .. database import get_db

bp = Blueprint('bank_accounts', __name__, template_folder='pages', url_prefix='/bank-accounts')


@bp.route('/')
@login_required
def home():
    db = get_db()
    show = request.args.get('show', 'active')  # 'active' | 'all'

    if show == 'all':
        rows = db.execute(
            "SELECT ref_num, bank_id, bank_name, priority, report_label, is_active "
            "FROM tbl_bank_account ORDER BY priority"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT ref_num, bank_id, bank_name, priority, report_label, is_active "
            "FROM tbl_bank_account WHERE is_active = 1 ORDER BY priority"
        ).fetchall()

    accounts = [dict(r) for r in rows]
    return render_template('bank_accounts/home.html', accounts=accounts, show=show)


@bp.route('/<int:ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(ref_num):
    db = get_db()
    row = db.execute(
        "SELECT ref_num, bank_id, bank_name, priority, report_label, is_active "
        "FROM tbl_bank_account WHERE ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        flash("Bank account not found.")
        return redirect(url_for('bank_accounts.home'))

    if request.method == 'POST':
        label = request.form.get('report_label', '').strip() or None
        db.execute(
            "UPDATE tbl_bank_account SET report_label=? WHERE ref_num=?",
            (label, ref_num)
        )
        db.commit()
        flash(f"Report label updated for {row['bank_name']}.")
        return redirect(url_for('bank_accounts.home'))

    return render_template('bank_accounts/edit.html', account=dict(row))


@bp.route('/<int:ref_num>/toggle-active', methods=['POST'])
@login_required
def toggle_active(ref_num):
    db = get_db()
    show = request.args.get('show', 'active')
    row = db.execute(
        "SELECT ref_num, bank_name, is_active FROM tbl_bank_account WHERE ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        flash("Bank account not found.")
        return redirect(url_for('bank_accounts.home', show=show))

    new_status = 0 if row['is_active'] else 1
    db.execute("UPDATE tbl_bank_account SET is_active=? WHERE ref_num=?", (new_status, ref_num))
    db.commit()
    label = "activated" if new_status else "deactivated"
    flash(f"{row['bank_name']} {label}.")
    return redirect(url_for('bank_accounts.home', show=show))
