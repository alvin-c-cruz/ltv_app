from flask import Blueprint, render_template, flash, request, redirect, url_for, send_file

from .. auth import login_required
from .. database import get_db
from .. transactions import Transaction

from .forms import DateForm
from . extensions import GenerateFixings, DownloadFixings, RecordFixings

bp = Blueprint("fixings", __name__, template_folder="pages", url_prefix="/fixings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    date_form = DateForm()
    db = get_db()

    if request.method == 'GET' and request.args.get('trade_date'):
        trade_date = request.args.get('trade_date')
    else:
        trade_date = str(date_form.trade_date.data)[:10]

    sql = "SELECT " \
          "     T.ref_num as id, " \
          "     T.bank_ref, T.code_ref, " \
          "     T.trade_date, T.value_date, " \
          "     B.bank_name, C.code, " \
          "     T.transaction_type, " \
          "     T.quantity, T.price, " \
          "     T.brokerage, T.commission, T.foreign_charge, T.stamp_duty, T.misc, " \
          "     (T.quantity * T.price) AS Amount, " \
          "     T.locked " \
          "FROM tbl_transaction AS T " \
          "INNER JOIN tbl_bank_account AS B ON B.ref_num = T.bank_ref " \
          "INNER JOIN tbl_code AS C ON C.ref_num = T.code_ref " \
          "INNER JOIN tbl_currency AS ccy ON ccy.ref_num = C.ccy_ref " \
          "WHERE T.trade_date=? AND T.transaction_type LIKE '%cu%' " \
          "ORDER BY ccy.priority, B.priority, C.code, T.transaction_type "

    rows = db.execute(sql, (trade_date, )).fetchall()

    def _qty(v):
        return '({:,.0f})'.format(abs(v)) if v < 0 else '{:,.0f}'.format(v)
    def _amt(v):
        return '({:,.2f})'.format(abs(v)) if v < 0 else '{:,.2f}'.format(v)

    grouped = {}
    for row in rows:
        bank = row['bank_name']
        if bank not in grouped:
            grouped[bank] = {'rows': [], 'total': 0.0}
        charges = (row['brokerage'] + row['commission'] + row['foreign_charge']
                   + row['stamp_duty'] + row['misc'])
        net = row['amount'] - charges
        grouped[bank]['rows'].append({
            'id':               row['id'],
            'value_date':       row['value_date'],
            'code':             row['code'],
            'transaction_type': row['transaction_type'],
            'quantity':         _qty(row['quantity']),
            'qty_neg':          row['quantity'] < 0,
            'price':            '{:,.4f}'.format(row['price']),
            'amount':           _amt(row['amount']),
            'amt_neg':          row['amount'] < 0,
            'charges':          _amt(charges),
            'charges_neg':      charges < 0,
            'net_amount':       _amt(net),
            'net_neg':          net < 0,
            'bank_ref':         row['bank_ref'],
            'code_ref':         row['code_ref'],
            'trade_date_raw':   row['trade_date'],
            'locked':           row['locked'],
            'value_date_raw':   row['value_date'],
            'qty_raw':          row['quantity'],
            'price_raw':        row['price'],
            'brokerage':        row['brokerage'],
            'commission':       row['commission'],
            'foreign_charge':   row['foreign_charge'],
            'stamp_duty':       row['stamp_duty'],
            'misc':             row['misc'],
        })
        grouped[bank]['total'] += row['amount']

    context = {
        "date_form":  date_form,
        "grouped":    grouped,
        "has_fixings": bool(rows),
        "trade_date": trade_date,
    }

    return render_template("fixings/home.html", **context)


@bp.route('/<ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(ref_num):
    from .. database import get_db
    transaction = Transaction(db=get_db())
    transaction.get(ref_num=ref_num)

    transaction_types = [(i, i) for i in ['Buy (Accu)', 'Buy (Accu-KO)', 'Sell (Decu)', 'Sell (Decu-KO)']]

    if request.method == 'POST':
        transaction.trade_date = request.form["trade_date"]
        transaction.value_date = request.form["value_date"]
        transaction.bank_ref = int(request.form["bank_ref"])
        transaction.code_ref = int(request.form["code_ref"])
        transaction.transaction_type = request.form["transaction_type"]
        transaction.quantity = int(request.form["quantity"])
        transaction.price = float(request.form["price"])
        transaction.brokerage = float(request.form["brokerage"])
        transaction.commission = float(request.form["commission"])
        transaction.foreign_charge = float(request.form["foreign_charge"])
        transaction.stamp_duty = float(request.form["stamp_duty"])
        transaction.misc = float(request.form["misc"])

        transaction.save()

        net_amount = transaction.quantity * transaction.price + (
                transaction.brokerage + transaction.commission + transaction.foreign_charge
                + transaction.stamp_duty + transaction.misc
        )
        flash("Updated net amount is " + '{:,.2f}'.format(net_amount))

        return redirect(url_for('fixings.home'))
    else:
        form = {
            "trade_date": transaction.trade_date,
            "value_date": transaction.value_date,
            "bank_ref": transaction.bank_ref,
            "code_ref": transaction.code_ref,
            "transaction_type": transaction.transaction_type,
            "quantity": transaction.quantity,
            "price": transaction.price,
            "brokerage": transaction.brokerage,
            "commission": transaction.commission,
            "foreign_charge": transaction.foreign_charge,
            "stamp_duty": transaction.stamp_duty,
            "misc": transaction.misc,
        }

    return render_template('fixings/edit.html', form=form, transaction_types=transaction_types, ref_num=ref_num)


@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from .. database import get_db
    transaction = Transaction(db=get_db())
    transaction.get(ref_num=ref_num)
    transaction.delete()

    flash(f"Fixing #{ref_num} has been deleted.")
    return redirect(url_for('fixings.home'))


@bp.route('/<ref_num>/unlock', methods=['GET'])
@login_required
def unlock(ref_num):
    from flask import abort
    from flask_login import current_user

    # Only superusers can unlock
    if current_user.role != 'superuser':
        abort(403)

    db = get_db()
    db.execute("UPDATE tbl_transaction SET locked=0 WHERE ref_num=?", (ref_num,))
    db.commit()

    flash(f"Transaction #{ref_num} has been unlocked.")
    return redirect(url_for('fixings.home'))


@bp.route('/add', methods=['POST'])
@login_required
def add():
    db = get_db()
    transaction = Transaction(db=db)
    transaction.trade_date    = request.form["trade_date"]
    transaction.value_date    = request.form["value_date"]
    transaction.bank_ref      = int(request.form["bank_ref"])
    transaction.code_ref      = int(request.form["code_ref"])
    transaction.transaction_type = request.form["transaction_type"]
    transaction.quantity      = int(request.form["quantity"])
    transaction.price         = float(request.form["price"])
    transaction.brokerage     = float(request.form.get("brokerage")     or 0)
    transaction.commission    = float(request.form.get("commission")    or 0)
    transaction.foreign_charge= float(request.form.get("foreign_charge")or 0)
    transaction.stamp_duty    = float(request.form.get("stamp_duty")    or 0)
    transaction.misc          = float(request.form.get("misc")          or 0)
    transaction.locked        = 0
    transaction.save()
    flash(f"Fixing transaction added for {transaction.trade_date}.")
    return redirect(url_for('fixings.home'))


@bp.route('/generate/<trade_date>')
@login_required
def generate(trade_date):
    db = get_db()
    fixing_data = GenerateFixings(trade_date).fixings
    fixings = DownloadFixings(db, trade_date, fixing_data)
    filename = fixings.filename
    return send_file('{}'.format(filename), as_attachment=True)


@bp.route('/record/<trade_date>')
@login_required
def record(trade_date):
    db = get_db()
    fixing_data = GenerateFixings(trade_date).fixings
    RecordFixings(db, fixing_data, trade_date)
    flash(f"Recorded fixings for {trade_date}.")
    return redirect(url_for('fixings.home', trade_date=trade_date))
