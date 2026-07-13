from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, g

from .. auth import login_required
from .. database import get_db

bp = Blueprint('charges', __name__, template_folder='pages', url_prefix='/charges')

_CHARGE_FIELDS = ('brokerage', 'commission', 'foreign_charge', 'stamp_duty', 'misc')
_NO_CHARGES_COND = " AND ".join(f"T.{f}=0" for f in _CHARGE_FIELDS)


def _query(db, table, date_from=None, date_to=None):
    params = []
    where_clause = f"""WHERE T.reviewed = 1
          AND T.locked = 0
          AND ({_NO_CHARGES_COND})
          AND T.no_charges = 0"""

    if date_from:
        where_clause += " AND T.trade_date >= ?"
        params.append(date_from)
    if date_to:
        where_clause += " AND T.trade_date <= ?"
        params.append(date_to)

    sql = f"""
        SELECT T.ref_num, T.trade_date, T.no_charges,
               B.bank_name, B.priority AS bank_priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity) * T.price) AS amount
        FROM {table} T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code         C ON C.ref_num = T.code_ref
        INNER JOIN tbl_currency    CY ON CY.ref_num = C.ccy_ref
        {where_clause}
        ORDER BY T.trade_date DESC, B.priority, C.code, T.transaction_type
    """
    return db.execute(sql, params).fetchall()


@bp.route('/')
@login_required
def home():
    db = get_db()

    # Get date range from query params, default to today
    today = datetime.today().strftime('%Y-%m-%d')
    date_from = request.args.get('date_from') or today
    date_to = request.args.get('date_to') or today

    rows_spot  = _query(db, 'tbl_transaction', date_from, date_to)
    rows_short = _query(db, 'tbl_transaction_short', date_from, date_to)

    def fmt(rows, source):
        result = []
        for r in rows:
            result.append({
                'ref_num':          r['ref_num'],
                'source':           source,
                'trade_date':       r['trade_date'],
                'bank_name':        r['bank_name'],
                'priority':         r['bank_priority'],
                'stock':            f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity':         '{:,.0f}'.format(abs(r['quantity'])),
                'price':            '{:,.4f}'.format(r['price']),
                'amount':           '{:,.2f}'.format(r['amount']),
            })
        return result

    all_rows = fmt(rows_spot, 'spot') + fmt(rows_short, 'short')

    grouped = defaultdict(lambda: {'rows': [], 'count': 0, 'priority': 0})
    for r in all_rows:
        bank = r['bank_name']
        grouped[bank]['rows'].append(r)
        grouped[bank]['count'] += 1
        grouped[bank]['priority'] = r['priority']
    grouped = dict(sorted(grouped.items(), key=lambda x: x[1]['priority']))

    total = sum(d['count'] for d in grouped.values())

    return render_template('charges/home.html',
                           grouped=grouped,
                           total=total,
                           date_from=date_from,
                           date_to=date_to)


@bp.route('/<source>/<int:ref_num>/no_charges', methods=['POST'])
@login_required
def mark_no_charges(source, ref_num):
    db = get_db()
    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'
    db.execute(f"UPDATE {table} SET no_charges=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction marked as no charges.")
    return redirect(url_for('charges.home'))


@bp.route('/<source>/<int:ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(source, ref_num):
    db = get_db()
    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'
    row = db.execute(
        f"SELECT T.*, B.bank_name, C.code, C.stock_name, T.transaction_type "
        f"FROM {table} T "
        f"INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref "
        f"INNER JOIN tbl_code C ON C.ref_num = T.code_ref "
        f"WHERE T.ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        flash("Transaction not found.")
        return redirect(url_for('charges.home'))

    if request.method == 'POST':
        fields = {f: float(request.form.get(f, 0) or 0) for f in _CHARGE_FIELDS}
        db.execute(
            f"UPDATE {table} SET brokerage=?, commission=?, foreign_charge=?, stamp_duty=?, misc=? WHERE ref_num=?",
            (*fields.values(), ref_num)
        )
        db.commit()
        total = sum(fields.values())
        flash(f"Charges updated. Total: {total:,.2f}")
        return redirect(url_for('charges.home'))

    context = {
        'ref_num':          ref_num,
        'source':           source,
        'trade_date':       row['trade_date'],
        'bank_name':        row['bank_name'],
        'stock':            f"{row['stock_name']} ({row['code']})",
        'transaction_type': row['transaction_type'],
        'quantity':         '{:,.0f}'.format(abs(row['quantity'])),
        'price':            '{:,.4f}'.format(row['price']),
        'amount':           '{:,.2f}'.format(abs(row['quantity']) * row['price']),
        'brokerage':        row['brokerage'] or 0,
        'commission':       row['commission'] or 0,
        'foreign_charge':   row['foreign_charge'] or 0,
        'stamp_duty':       row['stamp_duty'] or 0,
        'misc':             row['misc'] or 0,
    }
    return render_template('charges/edit.html', **context)
