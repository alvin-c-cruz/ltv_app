from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, g
from flask_login import current_user
from datetime import timedelta
from ...tz import ph_today

from .models import Transaction, TransactionShort
from .. auth import login_required
from .extensions import TransactionSummary, DownloadTradesDone, DownloadTradesDoneWithGainLoss

bp = Blueprint('transactions', __name__, template_folder='pages', url_prefix='/trades')


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        trade_date = request.form['trade_date']
    else:
        trade_date = request.args.get('trade_date', str(ph_today()))

    from ..database import get_db
    db = get_db()
    summary = TransactionSummary(db, trade_date)

    context = {
        "trade_date": trade_date,
        "transactions": summary.transactions,
        "short_transactions": summary.short_transactions,
        "accus": summary.accus,
        "decus": summary.decus
    }

    return render_template('transactions/home.html', **context)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    transaction_types = [(i, i) for i in ['Buy (Spot)', 'Sell (Spot)', 'Sell (Short)', 'Buy (Pay Short)',
                                          # 'Transfer-In', 'Transfer-Out'
                                          ]
                         ]

    if request.method == 'POST':
        error = ""

        trade_date = request.form["trade_date"]
        value_date = request.form["value_date"]
        bank_ref = int(request.form["bank_ref"])
        code_ref = int(request.form["code_ref"])
        transaction_type = request.form["transaction_type"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])

        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "bank_ref": bank_ref,
          "code_ref": code_ref,
          "transaction_type": transaction_type,
          "quantity": quantity,
          "price": price
        }

        if "Sell" in transaction_type or "Out" in transaction_type:
            if quantity > 0:
                error = "Sell transaction should have negative quantity."
        else:
            if quantity < 0:
                error = "Buy transaction should have position quantity"

        if not error:
            from .. database import get_db
            if transaction_type in ('Buy (Spot)', 'Sell (Spot)', 'Transfer-In', 'Transfer-Out'):
                new_transaction = Transaction(db=get_db(),
                  trade_date=trade_date,
                  value_date=value_date,
                  bank_ref=bank_ref,
                  code_ref=code_ref,
                  transaction_type=transaction_type,
                  quantity=quantity,
                  price=price
                  )
            else:
                new_transaction = TransactionShort(db=get_db(),
                  trade_date=trade_date,
                  value_date=value_date,
                  bank_ref=bank_ref,
                  code_ref=code_ref,
                  transaction_type=transaction_type,
                  quantity=quantity,
                  price=price
                  )

            new_transaction.save()

            flash(f"Transaction added: {transaction_type} {abs(quantity):,} shares.")
            return redirect(url_for('transactions.home', trade_date=trade_date))
        else:
            flash(error)
    else:
        trade_date = str(ph_today())
        value_date = str(ph_today() + timedelta(days=2))
        form = {
          "trade_date": trade_date,
          "value_date": value_date
        }

    context = {
        "form": form,
        "transaction_types": transaction_types
    }

    return render_template('transactions/add.html', **context)


@bp.route('/stock_transfer', methods=['GET', 'POST'])
@login_required
def stock_transfer():
    transaction_types = [(i, i) for i in ['Transfer-Out']]

    if request.method == 'POST':
        error = ""

        trade_date = request.form["trade_date"]
        value_date = request.form["value_date"]
        bank_ref = int(request.form["bank_ref"])
        code_ref = int(request.form["code_ref"])
        transaction_type = request.form["transaction_type"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])
        counter_bank_ref = int(request.form["counter_bank_ref"])

        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "bank_ref": bank_ref,
          "code_ref": code_ref,
          "transaction_type": transaction_type,
          "quantity": quantity,
          "price": price,
          "counter_bank_ref": counter_bank_ref
        }

        if "Sell" in transaction_type or "Out" in transaction_type:
            if quantity > 0:
                error = "Sell transaction should have negative quantity."
        else:
            if quantity < 0:
                error = "Buy transaction should have position quantity"

        if not error:
            from .. database import get_db
            transfer_out = Transaction(db=get_db(),
                  trade_date=trade_date,
                  value_date=value_date,
                  bank_ref=bank_ref,
                  code_ref=code_ref,
                  transaction_type=transaction_type,
                  quantity=quantity,
                  price=price,
                  counter_bank_ref=counter_bank_ref
                  )
            transfer_out.save()

            transfer_in = Transaction(db=get_db(),
                  trade_date=trade_date,
                  value_date=value_date,
                  bank_ref=counter_bank_ref,
                  code_ref=code_ref,
                  transaction_type="Transfer-In",
                  quantity=quantity * -1,
                  price=price,
                  counter_bank_ref=bank_ref
                  )
            transfer_in.save()

            flash(f"Transfer recorded: {abs(quantity):,} shares between accounts.")
            return redirect(url_for('transactions.home', trade_date=trade_date))
        else:
            flash(error)
    else:
        trade_date = str(ph_today())
        value_date = str(ph_today() + timedelta(days=2))
        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "transaction_type": 'Transfer-Out'
        }

    context = {
        "form": form,
        "transaction_types": transaction_types
    }

    return render_template('transactions/add_transfer.html', **context)


@bp.route('/<ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit(ref_num):
    from .. database import get_db
    transaction = Transaction(db=get_db())
    transaction.get(ref_num=ref_num)

    if transaction.locked and current_user.role != 'superuser':
        flash("This transaction is locked and cannot be edited.")
        return redirect(url_for('transactions.home'))

    transaction_types = [(i, i) for i in ['Buy (Spot)', 'Sell (Spot)', 'Transfer-In', 'Transfer-Out', "Stock Dividend"]]

    if request.method == 'POST':
        error = ""

        trade_date = request.form["trade_date"]
        value_date = request.form["value_date"]
        bank_ref = int(request.form["bank_ref"])
        code_ref = int(request.form["code_ref"])
        transaction_type = request.form["transaction_type"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])
        brokerage = float(request.form["brokerage"])
        commission = float(request.form["commission"])
        foreign_charge = float(request.form["foreign_charge"])
        stamp_duty = float(request.form["stamp_duty"])
        misc = float(request.form["misc"])
        counter_bank_ref = request.form.get("counter_bank_ref")
        if counter_bank_ref:
            counter_bank_ref = int(counter_bank_ref)

        form = {
            "trade_date": trade_date,
            "value_date": value_date,
            "bank_ref": bank_ref,
            "code_ref": code_ref,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "price": price,
            "brokerage": brokerage,
            "commission": commission,
            "foreign_charge": foreign_charge,
            "stamp_duty": stamp_duty,
            "misc": misc,
            "counter_bank_ref": counter_bank_ref,
        }

        if "Sell" in transaction_type or "Out" in transaction_type:
            if quantity > 0:
                error = "Sell transaction should have negative quantity."
        else:
            if quantity < 0:
                error = "Buy transaction should have position quantity"

        if not error:
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
            if request.form.get("counter_bank_ref"):
                transaction.counter_bank_ref = int(request.form["counter_bank_ref"])

            transaction.save()

            net_amount = transaction.quantity * transaction.price + (
                transaction.brokerage + transaction.commission + transaction.foreign_charge
                + transaction.stamp_duty + transaction.misc
            )
            flash("Updated net amount is " + '{:,.2f}'.format(net_amount))
            return redirect(url_for('transactions.edit', ref_num=ref_num))
        else:
            flash(error)
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
            "counter_bank_ref": transaction.counter_bank_ref,
        }

    context = {
        "form": form,
        "transaction_types": transaction_types,
        "ref_num": ref_num
    }

    return render_template('transactions/edit.html', **context)


@bp.route('/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete(ref_num):
    from .. database import get_db
    transaction = Transaction(db=get_db())
    transaction.get(ref_num=ref_num)

    if transaction.locked and current_user.role != 'superuser':
        flash("This transaction is locked and cannot be deleted.")
        return redirect(url_for('transactions.home'))

    transaction.delete()

    flash(f"Transaction #{ref_num} has been deleted.")
    return redirect(url_for('transactions.home'))


@bp.route('/short/<ref_num>/edit', methods=['GET', 'POST'])
@login_required
def edit_short(ref_num):
    from .. database import get_db
    transaction = TransactionShort(db=get_db())
    transaction.get(ref_num=ref_num)

    if transaction.locked and current_user.role != 'superuser':
        flash("This transaction is locked and cannot be edited.")
        return redirect(url_for('transactions.home'))

    transaction_types = [(i, i) for i in ['Sell (Short)', 'Buy (Pay Short)']]

    if request.method == 'POST':
        error = ""

        trade_date = request.form["trade_date"]
        value_date = request.form["value_date"]
        bank_ref = int(request.form["bank_ref"])
        code_ref = int(request.form["code_ref"])
        transaction_type = request.form["transaction_type"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])

        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "bank_ref": bank_ref,
          "code_ref": code_ref,
          "transaction_type": transaction_type,
          "quantity": quantity,
          "price": price
        }

        if "Sell" in transaction_type:
            if quantity > 0:
                error = "Sell transaction should have negative quantity."
        else:
            if quantity < 0:
                error = "Buy transaction should have position quantity"

        if not error:
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
            return redirect(url_for('transactions.edit_short', ref_num=ref_num))
        else:
            flash(error)
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
            "foreign_charge":transaction.foreign_charge,
            "stamp_duty": transaction.stamp_duty,
            "misc": transaction.misc,
        }

    context = {
        "form": form,
        "transaction_types": transaction_types,
        "ref_num": ref_num
    }

    return render_template('transactions/edit_short.html', **context)


@bp.route('/short/<ref_num>/delete', methods=['GET', 'POST'])
@login_required
def delete_short(ref_num):
    from .. database import get_db
    transaction = TransactionShort(db=get_db())
    transaction.get(ref_num=ref_num)

    if transaction.locked and current_user.role != 'superuser':
        flash("This transaction is locked and cannot be deleted.")
        return redirect(url_for('transactions.home'))

    transaction.delete()

    flash(f"Transaction #{ref_num} has been deleted.")
    return redirect(url_for('transactions.home'))


@bp.route('/download/<trade_date>', methods=['GET', 'POST'])
@login_required
def download(trade_date):
    from ..database import get_db
    db = get_db()
    summary = TransactionSummary(db, trade_date)
    if summary.is_empty():
        flash("No data to download.", category="error")
        return redirect(url_for("transactions.home"))
    else:
        filename = DownloadTradesDone(db=db, trade_date=trade_date, trade_summary=summary).filename
        return send_file('{}'.format(filename))


@bp.route('/download_with_gain_loss/<trade_date>', methods=['GET', 'POST'])
@login_required
def download_with_gain_loss(trade_date):
    from ..database import get_db
    db = get_db()
    summary = TransactionSummary(db, trade_date)
    if summary.is_empty():
        flash("No data to download.", category="error")
        return redirect(url_for("transactions.home"))
    else:
        filename = DownloadTradesDoneWithGainLoss(
            db=db,
            trade_date=trade_date,
            trade_summary=summary
        ).filename
        return send_file('{}'.format(filename))


@bp.route('/add_stock_dividends', methods=['GET', 'POST'])
@login_required
def add_stock_dividends():
    transaction_types = [
                            (i, i) for i in ['Stock Dividend', ]
                        ]

    if request.method == 'POST':
        error = ""

        trade_date = request.form["trade_date"]
        value_date = request.form["value_date"]
        bank_ref = int(request.form["bank_ref"])
        code_ref = int(request.form["code_ref"])
        transaction_type = request.form["transaction_type"]
        quantity = int(request.form["quantity"])
        price = float(request.form["price"])

        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "bank_ref": bank_ref,
          "code_ref": code_ref,
          "transaction_type": transaction_type,
          "quantity": quantity,
          "price": price
        }

        if "Sell" in transaction_type or "Out" in transaction_type:
            if quantity > 0:
                error = "Sell transaction should have negative quantity."
        else:
            if quantity < 0:
                error = "Buy transaction should have position quantity"

        if not error:
            from .. database import get_db
            new_transaction = Transaction(db=get_db(),
                  trade_date=trade_date,
                  value_date=value_date,
                  bank_ref=bank_ref,
                  code_ref=code_ref,
                  transaction_type=transaction_type,
                  quantity=quantity,
                  price=price
                  )

            new_transaction.save()

            flash(f"Stock dividend added: {abs(quantity):,} shares.")
            return redirect(url_for('transactions.home', trade_date=trade_date))
        else:
            flash(error)
    else:
        trade_date = str(ph_today())
        value_date = str(ph_today())
        form = {
          "trade_date": trade_date,
          "value_date": value_date,
          "transaction_type": "Stock Dividend"
        }

    context = {
        "form": form,
        "transaction_types": transaction_types
    }

    return render_template('transactions/add_stock_dividends.html', **context)
