from flask import Blueprint, render_template, redirect, url_for, flash, request

from ..auth import login_required

bp = Blueprint('stocks', __name__, template_folder='pages', url_prefix='/stocks')


def get_db():
    """Import get_db lazily to avoid circular import"""
    from ..database import get_db as _get_db
    return _get_db()


@bp.route('/')
@login_required
def home():
    """List all stock codes"""
    db = get_db()

    # Get all stocks with currency information
    rows = db.execute("""
        SELECT
            s.ref_num,
            s.code,
            s.company_name,
            s.stock_name,
            s.yahoo_ticker,
            s.security_code,
            s.ccy_ref,
            c.ccy_name
        FROM tbl_code s
        LEFT JOIN tbl_currency c ON s.ccy_ref = c.ref_num
        ORDER BY s.code
    """).fetchall()

    stocks = [dict(r) for r in rows]
    return render_template('stocks/home.html', stocks=stocks)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add new stock code"""
    db = get_db()

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        company_name = request.form.get('company_name', '').strip()
        stock_name = request.form.get('stock_name', '').strip()
        yahoo_ticker = request.form.get('yahoo_ticker', '').strip() or None
        security_code = request.form.get('security_code', '').strip() or None
        ccy_ref = request.form.get('ccy_ref') or None

        # Validation
        if not code:
            flash('Stock code is required.')
            return redirect(url_for('stocks.add'))

        # Check for duplicate code
        existing = db.execute(
            "SELECT ref_num FROM tbl_code WHERE code=?", (code,)
        ).fetchone()

        if existing:
            flash(f'Stock code "{code}" already exists.')
            return redirect(url_for('stocks.add'))

        # Insert new stock
        db.execute("""
            INSERT INTO tbl_code
            (code, company_name, stock_name, yahoo_ticker, security_code, ccy_ref)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code, company_name, stock_name, yahoo_ticker, security_code, ccy_ref))
        db.commit()

        flash(f'Stock code "{code}" added successfully.')
        return redirect(url_for('stocks.home'))

    # GET: Load currencies for dropdown
    currencies = db.execute(
        "SELECT ref_num, ccy_name FROM tbl_currency ORDER BY ccy_name"
    ).fetchall()

    return render_template('stocks/form.html',
                          stock=None,
                          currencies=[dict(c) for c in currencies],
                          mode='add')


@bp.route('/<int:ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(ref_num):
    """Edit existing stock code"""
    db = get_db()

    # Get stock
    row = db.execute(
        "SELECT * FROM tbl_code WHERE ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        flash("Stock code not found.")
        return redirect(url_for('stocks.home'))

    stock = dict(row)

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        company_name = request.form.get('company_name', '').strip()
        stock_name = request.form.get('stock_name', '').strip()
        yahoo_ticker = request.form.get('yahoo_ticker', '').strip() or None
        security_code = request.form.get('security_code', '').strip() or None
        ccy_ref = request.form.get('ccy_ref') or None

        # Validation
        if not code:
            flash('Stock code is required.')
            return redirect(url_for('stocks.edit', ref_num=ref_num))

        # Check for duplicate code (excluding current record)
        existing = db.execute(
            "SELECT ref_num FROM tbl_code WHERE code=? AND ref_num!=?",
            (code, ref_num)
        ).fetchone()

        if existing:
            flash(f'Stock code "{code}" already exists.')
            return redirect(url_for('stocks.edit', ref_num=ref_num))

        # Update stock
        db.execute("""
            UPDATE tbl_code
            SET code=?, company_name=?, stock_name=?,
                yahoo_ticker=?, security_code=?, ccy_ref=?
            WHERE ref_num=?
        """, (code, company_name, stock_name, yahoo_ticker,
              security_code, ccy_ref, ref_num))
        db.commit()

        flash(f'Stock code "{code}" updated successfully.')
        return redirect(url_for('stocks.home'))

    # GET: Load currencies for dropdown
    currencies = db.execute(
        "SELECT ref_num, ccy_name FROM tbl_currency ORDER BY ccy_name"
    ).fetchall()

    return render_template('stocks/form.html',
                          stock=stock,
                          currencies=[dict(c) for c in currencies],
                          mode='edit')


@bp.route('/<int:ref_num>/delete', methods=['POST'])
@login_required
def delete(ref_num):
    """Delete stock code"""
    db = get_db()

    # Get stock info for message
    row = db.execute(
        "SELECT code, company_name FROM tbl_code WHERE ref_num=?", (ref_num,)
    ).fetchone()

    if not row:
        flash("Stock code not found.")
        return redirect(url_for('stocks.home'))

    stock = dict(row)

    # Check if stock is referenced in transactions
    transaction_count = db.execute(
        "SELECT COUNT(*) as count FROM tbl_transaction WHERE code_ref=?", (ref_num,)
    ).fetchone()['count']

    if transaction_count > 0:
        flash(f'Cannot delete "{stock["code"]}" - it has {transaction_count} related transaction(s).')
        return redirect(url_for('stocks.home'))

    # Delete stock
    db.execute("DELETE FROM tbl_code WHERE ref_num=?", (ref_num,))
    db.commit()

    flash(f'Stock code "{stock["code"]}" deleted successfully.')
    return redirect(url_for('stocks.home'))
