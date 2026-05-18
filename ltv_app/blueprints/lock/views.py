from collections import defaultdict

from flask import Blueprint, render_template, redirect, url_for, request, flash

from .. auth import superuser_required
from .. database import get_db

bp = Blueprint('lock', __name__, template_folder='pages', url_prefix='/lock')


def _fetch_all(db):
    spot = db.execute("""
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
        ORDER BY B.priority, T.trade_date DESC, C.code, T.transaction_type
    """).fetchall()

    short = db.execute("""
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
        ORDER BY B.priority, T.trade_date DESC, C.code, T.transaction_type
    """).fetchall()

    contracts = db.execute("""
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
        ORDER BY a.priority, c.trade_date DESC, s.code, c.transaction_type
    """).fetchall()

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
    all_rows = _fetch_all(db)

    # collect all bank names in priority order (deduplicated)
    seen = {}
    for r in all_rows:
        if r['bank_name'] not in seen:
            seen[r['bank_name']] = r['priority']
    all_banks = sorted(seen.keys(), key=lambda b: seen[b])

    filter_banks = request.args.getlist('bank')

    rows = all_rows
    if filter_banks:
        rows = [r for r in all_rows if r['bank_name'] in filter_banks]

    grouped = _group_by_bank(rows)
    total = sum(d['count'] for d in grouped.values())

    return render_template('lock/home.html',
                           grouped=grouped,
                           total=total,
                           all_banks=all_banks,
                           filter_banks=filter_banks)


@bp.route('/<source>/<int:ref_num>/lock', methods=['POST'])
@superuser_required
def lock_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short', 'contract': 'tbl_stock_contract'}[source]
    db.execute(f"UPDATE {table} SET locked=1 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction locked.")
    filter_banks = request.form.getlist('bank')
    args = {'bank': filter_banks} if filter_banks else {}
    return redirect(url_for('lock.home', **args))


@bp.route('/<source>/<int:ref_num>/unlock', methods=['POST'])
@superuser_required
def unlock_txn(source, ref_num):
    db = get_db()
    table = {'spot': 'tbl_transaction', 'short': 'tbl_transaction_short', 'contract': 'tbl_stock_contract'}[source]
    db.execute(f"UPDATE {table} SET locked=0 WHERE ref_num=?", (ref_num,))
    db.commit()
    flash("Transaction unlocked.")
    return redirect(url_for('lock.home'))
