from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from datetime import datetime
from .. auth import login_required
from .. database import get_db

bp = Blueprint('review', __name__, template_folder='pages', url_prefix='/review')

_JOIN = (
    "FROM tbl_transaction T "
    "INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref "
    "INNER JOIN tbl_code C        ON C.ref_num = T.code_ref "
)


def _build_filter(filter_codes, filter_types, filter_banks=None):
    where = "WHERE T.reviewed = 0"
    params = []
    if filter_codes:
        where += " AND C.code IN ({})".format(','.join('?' * len(filter_codes)))
        params.extend(filter_codes)
    if filter_types:
        where += " AND T.transaction_type IN ({})".format(','.join('?' * len(filter_types)))
        params.extend(filter_types)
    if filter_banks:
        where += " AND B.bank_name IN ({})".format(','.join('?' * len(filter_banks)))
        params.extend(filter_banks)
    return where, params


def _bank_update_cond(filter_banks):
    """WHERE fragment + params for UPDATE statements that can't join to bank table."""
    if not filter_banks:
        return '', []
    ph = ','.join('?' * len(filter_banks))
    return (
        f" AND bank_ref IN (SELECT ref_num FROM tbl_bank_account WHERE bank_name IN ({ph}))",
        list(filter_banks),
    )


def _filter_args(filter_codes, filter_types, filter_banks):
    args = {}
    if filter_codes:
        args['code'] = filter_codes
    if filter_types:
        args['txn_type'] = filter_types
    if filter_banks:
        args['bank'] = filter_banks
    return args


def _fmt_qty(v):
    return '({:,.0f})'.format(abs(v)) if v < 0 else '{:,.0f}'.format(v)

def _fmt_amt(v):
    return '({:,.2f})'.format(abs(v)) if v < 0 else '{:,.2f}'.format(v)

def _fmt_date(s):
    try:
        d = datetime.strptime(s, '%Y-%m-%d')
        return f"{d.day} {d.strftime('%b')} {d.year}"
    except Exception:
        return s


@bp.route('/')
@login_required
def home():
    db = get_db()
    filter_codes = request.args.getlist('code')
    filter_types = request.args.getlist('txn_type')
    filter_banks = request.args.getlist('bank')

    codes = [r[0] for r in db.execute(
        "SELECT DISTINCT C.code " + _JOIN + "WHERE T.reviewed = 0 ORDER BY C.code"
    ).fetchall()]
    txn_types = [r[0] for r in db.execute(
        "SELECT DISTINCT T.transaction_type FROM tbl_transaction T "
        "WHERE T.reviewed = 0 ORDER BY T.transaction_type"
    ).fetchall()]
    all_banks = [r[0] for r in db.execute(
        "SELECT DISTINCT B.bank_name FROM tbl_bank_account B WHERE B.ref_num IN ("
        "  SELECT bank_ref FROM tbl_transaction      WHERE reviewed = 0 "
        "  UNION "
        "  SELECT bank_ref FROM tbl_transaction_short WHERE reviewed = 0 "
        "  UNION "
        "  SELECT bank_ref FROM tbl_stock_contract   WHERE reviewed = 0 "
        ") ORDER BY B.priority"
    ).fetchall()]

    # Spot transactions
    where, params = _build_filter(filter_codes, filter_types, filter_banks)
    rows = db.execute(
        "SELECT T.ref_num, T.trade_date, T.value_date, "
        "       B.bank_name, B.priority AS bank_priority, "
        "       C.code, C.stock_name, "
        "       T.transaction_type, T.quantity, T.price, "
        "       (T.quantity * T.price) AS amount "
        + _JOIN + where +
        " ORDER BY B.priority, T.trade_date DESC, C.code, T.transaction_type",
        params
    ).fetchall()

    grouped = {}
    for r in rows:
        bank = r['bank_name']
        if bank not in grouped:
            grouped[bank] = {'rows': [], 'count': 0}
        grouped[bank]['rows'].append({
            'id':               r['ref_num'],
            'trade_date':       _fmt_date(r['trade_date']),
            'value_date':       _fmt_date(r['value_date']),
            'code':             r['code'],
            'stock_name':       r['stock_name'],
            'transaction_type': r['transaction_type'],
            'quantity':         _fmt_qty(r['quantity']),
            'qty_neg':          r['quantity'] < 0,
            'price':            '{:,.4f}'.format(r['price']),
            'amount':           _fmt_amt(r['amount']),
            'amt_neg':          r['amount'] < 0,
        })
        grouped[bank]['count'] += 1

    total = sum(g['count'] for g in grouped.values())

    # Short transactions
    short_bank_cond = (" AND B.bank_name IN ({})".format(','.join('?' * len(filter_banks))) if filter_banks else '')
    short_rows = db.execute(
        "SELECT T.ref_num, T.trade_date, T.value_date, "
        "       B.bank_name, B.priority, C.code, C.stock_name, "
        "       T.transaction_type, T.quantity, T.price, "
        "       (T.quantity * T.price) AS amount "
        "FROM tbl_transaction_short T "
        "INNER JOIN tbl_bank_account B ON B.ref_num = T.bank_ref "
        "INNER JOIN tbl_code C ON C.ref_num = T.code_ref "
        f"WHERE T.reviewed = 0{short_bank_cond} "
        "ORDER BY B.priority, T.trade_date DESC, C.code",
        list(filter_banks)
    ).fetchall()

    grouped_short = {}
    for r in short_rows:
        bank = r['bank_name']
        if bank not in grouped_short:
            grouped_short[bank] = {'rows': [], 'count': 0}
        grouped_short[bank]['rows'].append({
            'id':               r['ref_num'],
            'trade_date':       _fmt_date(r['trade_date']),
            'value_date':       _fmt_date(r['value_date']),
            'code':             r['code'],
            'stock_name':       r['stock_name'],
            'transaction_type': r['transaction_type'],
            'quantity':         _fmt_qty(r['quantity']),
            'qty_neg':          r['quantity'] < 0,
            'price':            '{:,.4f}'.format(r['price']),
            'amount':           _fmt_amt(r['amount']),
            'amt_neg':          r['amount'] < 0,
        })
        grouped_short[bank]['count'] += 1

    total_short = sum(g['count'] for g in grouped_short.values())

    # Contracts (term sheets)
    contract_bank_cond = (" AND a.bank_name IN ({})".format(','.join('?' * len(filter_banks))) if filter_banks else '')
    contract_rows = db.execute(
        "SELECT c.ref_num, c.trade_date, a.bank_name, a.priority, "
        "       s.code, s.stock_name, c.transaction_type, "
        "       c.daily_shares, c.leveraged, c.spot, c.strike_rate, c.ko_rate, c.tenor "
        "FROM tbl_stock_contract c "
        "INNER JOIN tbl_bank_account a ON a.ref_num = c.bank_ref "
        "INNER JOIN tbl_code s ON s.ref_num = c.code_ref "
        f"WHERE c.reviewed = 0{contract_bank_cond} "
        "ORDER BY a.priority, c.trade_date DESC, s.code",
        list(filter_banks)
    ).fetchall()

    grouped_contracts = {}
    for r in contract_rows:
        bank = r['bank_name']
        if bank not in grouped_contracts:
            grouped_contracts[bank] = {'rows': [], 'count': 0}
        shares = (
            f'{r["daily_shares"]:,.0f} / {r["daily_shares"]*2:,.0f}'
            if r['leveraged'] == 'Yes'
            else f'{r["daily_shares"]:,.0f}'
        )
        grouped_contracts[bank]['rows'].append({
            'id':               r['ref_num'],
            'trade_date':       _fmt_date(r['trade_date']),
            'code':             r['code'],
            'stock_name':       r['stock_name'],
            'transaction_type': r['transaction_type'],
            'shares':           shares,
            'spot':             '{:,.4f}'.format(r['spot']),
            'strike':           '{:,.4f}'.format(r['spot'] * r['strike_rate'] / 100),
            'ko':               '{:,.4f}'.format(r['spot'] * r['ko_rate'] / 100),
            'tenor':            r['tenor'],
        })
        grouped_contracts[bank]['count'] += 1

    total_contracts = sum(g['count'] for g in grouped_contracts.values())

    return render_template('review/home.html',
                           grouped=grouped, total=total,
                           grouped_short=grouped_short, total_short=total_short,
                           grouped_contracts=grouped_contracts, total_contracts=total_contracts,
                           codes=codes, txn_types=txn_types, all_banks=all_banks,
                           filter_codes=filter_codes, filter_types=filter_types,
                           filter_banks=filter_banks)


@bp.route('/<int:ref_num>/data')
@login_required
def data(ref_num):
    db = get_db()
    r = db.execute(
        "SELECT T.trade_date, T.value_date, T.transaction_type, T.quantity, T.price, "
        "       T.brokerage, T.commission, T.foreign_charge, T.stamp_duty, T.misc "
        "FROM tbl_transaction T WHERE T.ref_num = ?", (ref_num,)
    ).fetchone()
    if r is None:
        return jsonify({}), 404
    return jsonify({
        'trade_date':       r['trade_date'],
        'value_date':       r['value_date'],
        'transaction_type': r['transaction_type'],
        'quantity':         r['quantity'],
        'price':            r['price'],
        'brokerage':        r['brokerage'] or 0,
        'commission':       r['commission'] or 0,
        'foreign_charge':   r['foreign_charge'] or 0,
        'stamp_duty':       r['stamp_duty'] or 0,
        'misc':             r['misc'] or 0,
    })


@bp.route('/<int:ref_num>/edit', methods=['POST'])
@login_required
def edit(ref_num):
    db = get_db()
    db.execute(
        "UPDATE tbl_transaction SET "
        "  trade_date = ?, value_date = ?, transaction_type = ?, "
        "  quantity = ?, price = ?, "
        "  brokerage = ?, commission = ?, foreign_charge = ?, stamp_duty = ?, misc = ? "
        "WHERE ref_num = ?",
        (
            request.form['trade_date'], request.form['value_date'],
            request.form['transaction_type'],
            request.form['quantity'], request.form['price'],
            request.form.get('brokerage', 0), request.form.get('commission', 0),
            request.form.get('foreign_charge', 0), request.form.get('stamp_duty', 0),
            request.form.get('misc', 0),
            ref_num,
        )
    )
    db.commit()
    flash("Transaction updated.")
    return redirect(url_for('review.home', **_filter_args(
        request.form.getlist('code'),
        request.form.getlist('txn_type'),
        request.form.getlist('bank'),
    )))


@bp.route('/<int:ref_num>/mark', methods=['POST'])
@login_required
def mark(ref_num):
    db = get_db()
    db.execute("UPDATE tbl_transaction SET reviewed = 1 WHERE ref_num = ?", (ref_num,))
    db.commit()
    return redirect(url_for('review.home', **_filter_args(
        request.form.getlist('code'),
        request.form.getlist('txn_type'),
        request.form.getlist('bank'),
    )))


@bp.route('/mark-all', methods=['POST'])
@login_required
def mark_all():
    db = get_db()
    filter_codes = request.form.getlist('code')
    filter_types = request.form.getlist('txn_type')
    filter_banks = request.form.getlist('bank')
    where, params = _build_filter(filter_codes, filter_types, filter_banks)

    n = db.execute("SELECT COUNT(*) " + _JOIN + where, params).fetchone()[0]
    db.execute(
        "UPDATE tbl_transaction SET reviewed = 1 WHERE ref_num IN "
        "(SELECT T.ref_num " + _JOIN + where + ")",
        params
    )
    db.commit()
    flash(f"Marked {n} transaction{'s' if n != 1 else ''} as reviewed.")
    return redirect(url_for('review.home', **_filter_args(filter_codes, filter_types, filter_banks)))


@bp.route('/short/<int:ref_num>/mark', methods=['POST'])
@login_required
def mark_short(ref_num):
    db = get_db()
    db.execute("UPDATE tbl_transaction_short SET reviewed = 1 WHERE ref_num = ?", (ref_num,))
    db.commit()
    return redirect(url_for('review.home', **_filter_args(
        [], [], request.form.getlist('bank')
    )))


@bp.route('/short/mark-all', methods=['POST'])
@login_required
def mark_all_short():
    db = get_db()
    filter_banks = request.form.getlist('bank')
    cond, params = _bank_update_cond(filter_banks)
    n = db.execute(f"SELECT COUNT(*) FROM tbl_transaction_short WHERE reviewed = 0{cond}", params).fetchone()[0]
    db.execute(f"UPDATE tbl_transaction_short SET reviewed = 1 WHERE reviewed = 0{cond}", params)
    db.commit()
    flash(f"Marked {n} short transaction{'s' if n != 1 else ''} as reviewed.")
    return redirect(url_for('review.home', **_filter_args([], [], filter_banks)))


@bp.route('/contract/<int:ref_num>/mark', methods=['POST'])
@login_required
def mark_contract(ref_num):
    db = get_db()
    db.execute("UPDATE tbl_stock_contract SET reviewed = 1 WHERE ref_num = ?", (ref_num,))
    db.commit()
    return redirect(url_for('review.home', **_filter_args(
        [], [], request.form.getlist('bank')
    )))


@bp.route('/contract/mark-all', methods=['POST'])
@login_required
def mark_all_contracts():
    db = get_db()
    filter_banks = request.form.getlist('bank')
    cond, params = _bank_update_cond(filter_banks)
    n = db.execute(f"SELECT COUNT(*) FROM tbl_stock_contract WHERE reviewed = 0{cond}", params).fetchone()[0]
    db.execute(f"UPDATE tbl_stock_contract SET reviewed = 1 WHERE reviewed = 0{cond}", params)
    db.commit()
    flash(f"Marked {n} contract{'s' if n != 1 else ''} as reviewed.")
    return redirect(url_for('review.home', **_filter_args([], [], filter_banks)))
