from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, request, flash

from .. auth import superuser_required
from .. database import get_db

bp = Blueprint('lock', __name__, template_folder='pages', url_prefix='/lock')


def _fetch_all(db, date_from=None, date_to=None):
    params_spot = []
    params_short = []
    params_contracts = []

    date_cond_spot = ""
    date_cond_short = ""
    date_cond_contracts = ""

    if date_from:
        date_cond_spot += " AND T.trade_date >= ?"
        params_spot.append(date_from)
        date_cond_short += " AND T.trade_date >= ?"
        params_short.append(date_from)
        date_cond_contracts += " AND c.trade_date >= ?"
        params_contracts.append(date_from)
    if date_to:
        date_cond_spot += " AND T.trade_date <= ?"
        params_spot.append(date_to)
        date_cond_short += " AND T.trade_date <= ?"
        params_short.append(date_to)
        date_cond_contracts += " AND c.trade_date <= ?"
        params_contracts.append(date_to)

    spot = db.execute(f"""
        SELECT T.ref_num, 'spot' AS source,
               B.bank_name, B.priority,
               C.code, C.stock_name, T.trade_date,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code         C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND (T.no_charges = 1 OR (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) > 0)
          {date_cond_spot}
        ORDER BY B.priority, T.trade_date DESC, C.code, T.transaction_type
    """, params_spot).fetchall()

    short = db.execute(f"""
        SELECT T.ref_num, 'short' AS source,
               B.bank_name, B.priority,
               C.code, C.stock_name, T.trade_date,
               T.transaction_type, T.quantity, T.price,
               (ABS(T.quantity)*T.price) AS amount,
               (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) AS charges
        FROM tbl_transaction_short T
        INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref
        INNER JOIN tbl_code         C ON C.ref_num = T.code_ref
        WHERE T.reviewed = 1
          AND T.locked = 0
          AND (T.no_charges = 1 OR (T.brokerage+T.commission+T.foreign_charge+T.stamp_duty+T.misc) > 0)
          {date_cond_short}
        ORDER BY B.priority, T.trade_date DESC, C.code, T.transaction_type
    """, params_short).fetchall()

    contracts = db.execute(f"""
        SELECT c.ref_num, 'contract' AS source,
               a.bank_name, a.priority,
               s.code, s.stock_name, c.trade_date,
               c.transaction_type,
               c.daily_shares AS quantity, c.spot AS price,
               0 AS amount, 0 AS charges
        FROM tbl_stock_contract c
        INNER JOIN tbl_bank_account a ON a.ref_num = c.bank_ref
        INNER JOIN tbl_code         s ON s.ref_num = c.code_ref
        WHERE c.reviewed = 1
          AND c.locked = 0
          {date_cond_contracts}
        ORDER BY a.priority, c.trade_date DESC, s.code, c.transaction_type
    """, params_contracts).fetchall()

    def fmt(rows):
        result = []
        for r in rows:
            result.append({
                'ref_num':          r['ref_num'],
                'source':           r['source'],
                'trade_date':       r['trade_date'],
                'bank_name':        r['bank_name'],
                'priority':         r['priority'],
                'code':             r['code'],
                'stock_name':       r['stock_name'],
                'stock':            f"{r['stock_name']} ({r['code']})",
                'transaction_type': r['transaction_type'],
                'quantity':         '{:,.0f}'.format(abs(r['quantity'])),
                'price':            '{:,.4f}'.format(r['price']),
                'amount':           '{:,.2f}'.format(r['amount']),
                'charges':          '{:,.2f}'.format(r['charges']),
            })
        return result

    return fmt(spot) + fmt(short) + fmt(contracts)


def _group_by_bank(rows):
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
    today = datetime.today().strftime('%Y-%m-%d')
    date_from = request.args.get('date_from') or today
    date_to = request.args.get('date_to') or today

    all_rows = _fetch_all(db, date_from, date_to)

    grouped = _group_by_bank(all_rows)
    total = sum(d['count'] for d in grouped.values())

    return render_template('lock/home.html',
                           grouped=grouped,
                           total=total,
                           date_from=date_from,
                           date_to=date_to)


@bp.route('/<source>/<int:ref_num>/lock', methods=['POST'])
@superuser_required
def lock_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short', 'contract': 'tbl_stock_contract'}[source]
    db.execute(f"UPDATE {table} SET locked=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction locked.")
    return redirect(url_for('lock.home'))


@bp.route('/lock-multiple', methods=['POST'])
@superuser_required
def lock_multiple():
    import json
    db = get_db()

    # Parse transactions JSON
    transactions_json = request.form.get('transactions', '[]')
    transactions = json.loads(transactions_json)

    if not transactions:
        flash("No transactions selected.")
        return redirect(url_for('lock.home'))

    # Lock each transaction
    table_map = {
        'spot': 'tbl_transaction',
        'short': 'tbl_transaction_short',
        'contract': 'tbl_stock_contract'
    }

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
    return redirect(url_for('lock.home'))


@bp.route('/<source>/<int:ref_num>/unlock', methods=['POST'])
@superuser_required
def unlock_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short', 'contract': 'tbl_stock_contract'}[source]
    db.execute(f"UPDATE {table} SET locked=0 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction unlocked.")
    return redirect(url_for('lock.home'))
