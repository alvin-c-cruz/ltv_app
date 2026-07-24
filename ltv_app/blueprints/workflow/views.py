from collections import defaultdict
import json

from flask import Blueprint, render_template, redirect, url_for, request, flash, abort

from .. auth import login_required, superuser_required
from .. database import get_db
from ... tz import ph_today

bp = Blueprint('workflow', __name__, template_folder='pages', url_prefix='/workflow')

_CHARGE_FIELDS = ('brokerage', 'commission', 'foreign_charge', 'stamp_duty', 'misc')
_NO_CHARGES_COND = " AND ".join(f"T.{f}=0" for f in _CHARGE_FIELDS)


def _fetch_review(db, date_from=None, date_to=None):
    """Fetch unreviewed transactions (Review section)."""
    params_spot = []
    params_short = []

    date_cond_spot = ""
    date_cond_short = ""

    if date_from:
        date_cond_spot += " AND T.trade_date >= ?"
        params_spot.append(date_from)
        date_cond_short += " AND T.trade_date >= ?"
        params_short.append(date_from)
    if date_to:
        date_cond_spot += " AND T.trade_date <= ?"
        params_spot.append(date_to)
        date_cond_short += " AND T.trade_date <= ?"
        params_short.append(date_to)

    spot = db.execute(f"""
        SELECT T.ref_num, 'spot' AS source, T.trade_date, T.value_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity) * T.price) AS amount
        FROM tbl_transaction T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 0
          {date_cond_spot}
        ORDER BY T.trade_date DESC, B.priority, C.code
    """, params_spot).fetchall()

    short = db.execute(f"""
        SELECT T.ref_num, 'short' AS source, T.trade_date, T.value_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity) * T.price) AS amount
        FROM tbl_transaction_short T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 0
          {date_cond_short}
        ORDER BY T.trade_date DESC, B.priority, C.code
    """, params_short).fetchall()

    def fmt(rows, source):
        result = []
        for r in rows:
            result.append({
                'ref_num': r['ref_num'],
                'source': source,
                'trade_date': r['trade_date'],
                'value_date': r['value_date'],
                'bank_name': r['bank_name'],
                'priority': r['priority'],
                'stock': f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity': '{:,.0f}'.format(abs(r['quantity'])),
                'price': '{:,.4f}'.format(r['price']),
                'amount': '{:,.2f}'.format(r['amount']),
                'is_fixing': source == 'spot' and 'cu' in r['transaction_type'].lower(),
            })
        return result

    return fmt(spot, 'spot') + fmt(short, 'short')


def _fetch_charges(db, date_from=None, date_to=None):
    """Fetch reviewed transactions with missing charges (Charges section)."""
    params = []
    date_cond = ""
    if date_from:
        date_cond += " AND T.trade_date >= ?"
        params.append(date_from)
    if date_to:
        date_cond += " AND T.trade_date <= ?"
        params.append(date_to)

    spot = db.execute(f"""
        SELECT T.ref_num, 'spot' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity) * T.price) AS amount
        FROM tbl_transaction T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND ({_NO_CHARGES_COND})
          AND T.no_charges = 0
          {date_cond}
        ORDER BY T.trade_date DESC, B.priority, C.code
    """, params).fetchall()

    short = db.execute(f"""
        SELECT T.ref_num, 'short' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity) * T.price) AS amount
        FROM tbl_transaction_short T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND ({_NO_CHARGES_COND})
          AND T.no_charges = 0
          {date_cond}
        ORDER BY T.trade_date DESC, B.priority, C.code
    """, params).fetchall()

    def fmt(rows, source):
        result = []
        for r in rows:
            result.append({
                'ref_num': r['ref_num'],
                'source': source,
                'trade_date': r['trade_date'],
                'bank_name': r['bank_name'],
                'priority': r['priority'],
                'stock': f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity': '{:,.0f}'.format(abs(r['quantity'])),
                'price': '{:,.4f}'.format(r['price']),
                'amount': '{:,.2f}'.format(r['amount']),
                'is_fixing': source == 'spot' and 'cu' in r['transaction_type'].lower(),
            })
        return result

    return fmt(spot, 'spot') + fmt(short, 'short')


def _fetch_lock(db, date_from=None, date_to=None):
    """Fetch reviewed transactions with charges ready to lock (Lock section)."""
    params_spot = []
    params_short = []
    date_cond_spot = ""
    date_cond_short = ""

    if date_from:
        date_cond_spot += " AND T.trade_date >= ?"
        params_spot.append(date_from)
        date_cond_short += " AND T.trade_date >= ?"
        params_short.append(date_from)
    if date_to:
        date_cond_spot += " AND T.trade_date <= ?"
        params_spot.append(date_to)
        date_cond_short += " AND T.trade_date <= ?"
        params_short.append(date_to)

    spot = db.execute(f"""
        SELECT T.ref_num, 'spot' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND (T.no_charges = 1 OR (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) > 0)
          {date_cond_spot}
        ORDER BY B.priority, T.trade_date DESC, C.code
    """, params_spot).fetchall()

    short = db.execute(f"""
        SELECT T.ref_num, 'short' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction_short T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND (T.no_charges = 1 OR (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) > 0)
          {date_cond_short}
        ORDER BY B.priority, T.trade_date DESC, C.code
    """, params_short).fetchall()

    def fmt(rows):
        result = []
        for r in rows:
            net = r['amount'] + r['charges'] if r['quantity'] >= 0 else r['amount'] - r['charges']
            result.append({
                'ref_num': r['ref_num'],
                'source': r['source'],
                'trade_date': r['trade_date'],
                'bank_name': r['bank_name'],
                'priority': r['priority'],
                'code': r['code'],
                'stock_name': r['stock_name'],
                'stock': f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity': '{:,.0f}'.format(abs(r['quantity'])),
                'price': '{:,.4f}'.format(r['price']),
                'amount': '{:,.2f}'.format(r['amount']),
                'charges': '{:,.2f}'.format(r['charges']),
                'net_amount': '{:,.2f}'.format(net),
                'is_fixing': r['source'] == 'spot' and 'cu' in r['transaction_type'].lower(),
            })
        return result

    return fmt(spot) + fmt(short)


def _fetch_locked(db, date_from=None, date_to=None):
    """Fetch locked transactions (Locked section)."""
    params_spot = []
    params_short = []
    date_cond_spot = ""
    date_cond_short = ""

    if date_from:
        date_cond_spot += " AND T.trade_date >= ?"
        params_spot.append(date_from)
        date_cond_short += " AND T.trade_date >= ?"
        params_short.append(date_from)
    if date_to:
        date_cond_spot += " AND T.trade_date <= ?"
        params_spot.append(date_to)
        date_cond_short += " AND T.trade_date <= ?"
        params_short.append(date_to)

    spot = db.execute(f"""
        SELECT T.ref_num, 'spot' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.locked = 1
          {date_cond_spot}
        ORDER BY B.priority, T.trade_date DESC, C.code
    """, params_spot).fetchall()

    short = db.execute(f"""
        SELECT T.ref_num, 'short' AS source, T.trade_date,
               B.bank_name, B.priority,
               C.code, C.stock_name,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction_short T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code C ON C.ref_num = T.code_ref
        WHERE T.locked = 1
          {date_cond_short}
        ORDER BY B.priority, T.trade_date DESC, C.code
    """, params_short).fetchall()

    def fmt(rows):
        result = []
        for r in rows:
            net = r['amount'] + r['charges'] if r['quantity'] >= 0 else r['amount'] - r['charges']
            result.append({
                'ref_num': r['ref_num'],
                'source': r['source'],
                'trade_date': r['trade_date'],
                'bank_name': r['bank_name'],
                'priority': r['priority'],
                'stock': f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity': '{:,.0f}'.format(abs(r['quantity'])),
                'price': '{:,.4f}'.format(r['price']),
                'amount': '{:,.2f}'.format(r['amount']),
                'charges': '{:,.2f}'.format(r['charges']),
                'net_amount': '{:,.2f}'.format(net),
                'is_fixing': r['source'] == 'spot' and 'cu' in r['transaction_type'].lower(),
            })
        return result

    return fmt(spot) + fmt(short)


def _group_by_bank(rows):
    """Group rows by bank name."""
    grouped = defaultdict(lambda: {'rows': [], 'count': 0, 'priority': 0})
    for r in rows:
        bank = r['bank_name']
        grouped[bank]['rows'].append(r)
        grouped[bank]['count'] += 1
        grouped[bank]['priority'] = r['priority']
    return dict(sorted(grouped.items(), key=lambda x: x[1]['priority']))


@bp.route('/')
@superuser_required
def home():
    db = get_db()

    # Get date range from query params, default to today
    today = str(ph_today())
    date_from = request.args.get('date_from') or today
    date_to = request.args.get('date_to') or today

    # Fetch all sections
    review_rows = _fetch_review(db, date_from, date_to)
    charges_rows = _fetch_charges(db, date_from, date_to)
    lock_rows = _fetch_lock(db, date_from, date_to)
    locked_rows = _fetch_locked(db, date_from, date_to)

    # Group by bank
    review_grouped = _group_by_bank(review_rows)
    charges_grouped = _group_by_bank(charges_rows)
    lock_grouped = _group_by_bank(lock_rows)
    locked_grouped = _group_by_bank(locked_rows)

    # Calculate totals
    review_total = sum(d['count'] for d in review_grouped.values())
    charges_total = sum(d['count'] for d in charges_grouped.values())
    lock_total = sum(d['count'] for d in lock_grouped.values())
    locked_total = sum(d['count'] for d in locked_grouped.values())

    return render_template('workflow/home.html',
                           date_from=date_from,
                           date_to=date_to,
                           review_grouped=review_grouped,
                           review_total=review_total,
                           charges_grouped=charges_grouped,
                           charges_total=charges_total,
                           lock_grouped=lock_grouped,
                           lock_total=lock_total,
                           locked_grouped=locked_grouped,
                           locked_total=locked_total)


# Review actions
@bp.route('/review/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def review_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short'}[source]
    db.execute(f"UPDATE {table} SET reviewed=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction reviewed.")
    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


@bp.route('/review-multiple', methods=['POST'])
@superuser_required
def review_multiple():
    db = get_db()
    transactions_json = request.form.get('transactions', '[]')
    transactions = json.loads(transactions_json)

    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not transactions:
        flash("No transactions selected.")
        return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))

    table_map = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short'}
    reviewed_count = 0
    for txn in transactions:
        source = txn.get('source')
        ref_num = txn.get('ref_num')
        if source in table_map and ref_num:
            table = table_map[source]
            db.execute(f"UPDATE {table} SET reviewed=1 WHERE ref_num=?", (ref_num,))
            reviewed_count += 1

    db.commit()
    flash(f"{reviewed_count} transaction{'s' if reviewed_count != 1 else ''} reviewed.")
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


# Charges actions
@bp.route('/charges/<source>/<int:ref_num>/data', methods=['GET'])
@superuser_required
def get_charges_data(source, ref_num):
    """Fetch transaction data for the charges modal."""
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
        return {'error': 'Transaction not found'}, 404

    data = {
        'bank_name': row['bank_name'],
        'stock': f"{row['stock_name']} ({row['code']})",
        'transaction_type': row['transaction_type'],
        'quantity': '{:,.0f}'.format(abs(row['quantity'])),
        'price': '{:,.4f}'.format(row['price']),
        'amount': '{:,.2f}'.format(abs(row['quantity']) * row['price']),
        'brokerage': row['brokerage'] or 0,
        'commission': row['commission'] or 0,
        'foreign_charge': row['foreign_charge'] or 0,
        'stamp_duty': row['stamp_duty'] or 0,
        'misc': row['misc'] or 0,
    }

    return data


@bp.route('/charges/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def edit_charges(source, ref_num):
    """Save charges from modal form."""
    db = get_db()
    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'

    fields = {
        'brokerage': float(request.form.get('brokerage', 0) or 0),
        'commission': float(request.form.get('commission', 0) or 0),
        'foreign_charge': float(request.form.get('foreign_charge', 0) or 0),
        'stamp_duty': float(request.form.get('stamp_duty', 0) or 0),
        'misc': float(request.form.get('misc', 0) or 0)
    }

    db.execute(
        f"UPDATE {table} SET brokerage=?, commission=?, foreign_charge=?, stamp_duty=?, misc=? WHERE ref_num=?",
        (*fields.values(), ref_num)
    )
    db.commit()

    total = sum(fields.values())
    flash(f"Charges updated. Total: {total:,.2f}")
    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


@bp.route('/charges/<source>/<int:ref_num>/no_charges', methods=['POST'])
@superuser_required
def mark_no_charges(source, ref_num):
    db = get_db()
    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'
    db.execute(f"UPDATE {table} SET no_charges=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction marked as no charges.")
    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


# Edit actions
@bp.route('/edit/<source>/<int:ref_num>/data', methods=['GET'])
@superuser_required
def get_edit_data(source, ref_num):
    """Fetch transaction data for the edit modal."""
    db = get_db()

    # Fetch dropdown options
    banks = db.execute(
        "SELECT ref_num, bank_name FROM tbl_bank_account ORDER BY priority, bank_name"
    ).fetchall()

    stocks = db.execute(
        "SELECT ref_num, code, stock_name FROM tbl_code ORDER BY code"
    ).fetchall()

    transaction_types = db.execute(
        "SELECT DISTINCT transaction_type FROM tbl_transaction_type ORDER BY transaction_type"
    ).fetchall()

    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'
    row = db.execute(
        f"SELECT T.*, B.bank_name, C.code, C.stock_name "
        f"FROM {table} T "
        f"INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref "
        f"INNER JOIN tbl_code C ON C.ref_num = T.code_ref "
        f"WHERE T.ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        return {'error': 'Transaction not found'}, 404

    data = {
        'source': source,
        'trade_date': row['trade_date'],
        'value_date': row['value_date'],
        'bank_ref': row['bank_ref'],
        'code_ref': row['code_ref'],
        'transaction_type': row['transaction_type'],
        'quantity_raw': row['quantity'],
        'price_raw': row['price'],
        'brokerage': row['brokerage'] or 0,
        'commission': row['commission'] or 0,
        'foreign_charge': row['foreign_charge'] or 0,
        'stamp_duty': row['stamp_duty'] or 0,
        'misc': row['misc'] or 0,
        'banks': [{'ref_num': b['ref_num'], 'bank_name': b['bank_name']} for b in banks],
        'stocks': [{'ref_num': s['ref_num'], 'code': s['code'], 'stock_name': s['stock_name']} for s in stocks],
        'transaction_types': [t['transaction_type'] for t in transaction_types],
    }

    return data


@bp.route('/edit/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def save_edit(source, ref_num):
    """Save edited transaction data."""
    db = get_db()

    trade_date = request.form.get('trade_date')
    value_date = request.form.get('value_date')
    bank_ref = int(request.form.get('bank_ref'))
    code_ref = int(request.form.get('code_ref'))
    transaction_type = request.form.get('transaction_type')
    quantity = float(request.form.get('quantity', 0))
    price = float(request.form.get('price', 0))

    table = 'tbl_transaction' if source == 'spot' else 'tbl_transaction_short'

    fields = {
        'brokerage': float(request.form.get('brokerage', 0) or 0),
        'commission': float(request.form.get('commission', 0) or 0),
        'foreign_charge': float(request.form.get('foreign_charge', 0) or 0),
        'stamp_duty': float(request.form.get('stamp_duty', 0) or 0),
        'misc': float(request.form.get('misc', 0) or 0)
    }

    db.execute(
        f"UPDATE {table} SET trade_date=?, value_date=?, bank_ref=?, code_ref=?, "
        f"transaction_type=?, quantity=?, price=?, "
        f"brokerage=?, commission=?, foreign_charge=?, stamp_duty=?, misc=? WHERE ref_num=?",
        (trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price,
         fields['brokerage'], fields['commission'], fields['foreign_charge'],
         fields['stamp_duty'], fields['misc'], ref_num)
    )
    db.commit()
    flash("Transaction updated successfully.")

    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


# Lock actions
@bp.route('/lock/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def lock_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short'}[source]
    db.execute(f"UPDATE {table} SET locked=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction locked.")
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


@bp.route('/lock-multiple', methods=['POST'])
@superuser_required
def lock_multiple():
    db = get_db()
    transactions_json = request.form.get('transactions', '[]')
    transactions = json.loads(transactions_json)

    # Preserve date range
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if not transactions:
        flash("No transactions selected.")
        return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))

    table_map = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short'}
    locked_count = 0
    for txn in transactions:
        source = txn.get('source')
        ref_num = txn.get('ref_num')
        if source in table_map and ref_num:
            table = table_map[source]
            db.execute(f"UPDATE {table} SET locked=1 WHERE ref_num=?", (ref_num,))
            locked_count += 1

    db.commit()
    flash(f"{locked_count} transaction{'s' if locked_count != 1 else ''} locked.")
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))


@bp.route('/delete/<source>/<int:ref_num>', methods=['POST'])
@superuser_required
def delete_txn(source, ref_num):
    db = get_db()
    if source == 'short':
        db.execute("DELETE FROM tbl_transaction_short WHERE ref_num=?", (ref_num,))
    elif source == 'spot':
        db.execute("DELETE FROM tbl_transaction WHERE ref_num=?", (ref_num,))
    else:
        abort(400)
    db.commit()
    flash("Transaction deleted.")
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    return redirect(url_for('workflow.home', date_from=date_from, date_to=date_to))
