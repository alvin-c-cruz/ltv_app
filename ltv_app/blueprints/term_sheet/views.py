import datetime

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, g
from flask_login import current_user

from .models import TermSheet, StockContract, FixingSchedule, CreateSchedules, next_day

from .. database import get_db
from .. auth import login_required

bp = Blueprint("term_sheet", __name__, template_folder="pages", url_prefix="/term-sheet")


@bp.route("/<bank_id>", methods=["GET", "POST"])
@login_required
def home(bank_id):
    db = get_db()

    row = db.execute("SELECT ref_num, bank_name FROM tbl_bank_account WHERE bank_id=?", (bank_id,)).fetchone()
    bank_ref, bank_name = row['ref_num'], row['bank_name']

    if request.method == "POST":
        status = "all"
    else:
        status = "active"

    accus = TermSheet(
        db=db,
        bank_ref=bank_ref,
        transaction_type="ACCU",
        status=status
    ).web()

    decus = TermSheet(
        db=db,
        bank_ref=bank_ref,
        transaction_type="DECU",
        status=status
    ).web()

    return render_template('term_sheet/home.html', bank_name=bank_name, accus=accus, decus=decus)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    db = get_db()

    codes = db.execute("SELECT ref_num, code, stock_name FROM tbl_code;").fetchall()
    tenors = [
        ("1m", "1 month"),
        ("2m", "2 month"),
        ("3m", "3 month"),
        ("4m", "4 month"),
        ("5m", "5 month"),
        ("6m", "6 month"),
        ("7m", "7 month"),
        ("8m", "8 month"),
        ("9m", "9 month"),
        ("10m", "10 month"),
        ("11m", "11 month"),
        ("12m", "12 month"),
        ("13m", "13 month"),
        ("14m", "14 month"),
        ("15m", "15 month"),
    ]
    frequencies = [
        ("monthly", "Monthly"),
        ("bi-monthly", "Bi-Weekly"),
        ("weekly", "Weekly"),
    ]
    gtds = [
        ("No", "No"),
        ("Yes", "Yes"),
        ("1m", "1 month"),
        ("2m", "2 month"),
        ("3m", "3 month"),
        ("4m", "4 month"),
    ]


    if request.method == "POST":
        form = request.form

        ts = StockContract(db=db)
        ts.reference = next_reference(db, int(form.get('bank_ref')), int(form.get('code_ref')),
                                      form.get('transaction_type'))
        ts.bank_ref = int(form.get('bank_ref'))
        ts.code_ref = int(form.get('code_ref'))
        ts.transaction_type = form.get('transaction_type')
        trade_date = ts.trade_date = form.get('trade_date')
        start_date = ts.start_date = form.get('start_date')
        ts.daily_shares = int(form.get('daily_shares'))
        ts.leveraged = form.get('leveraged')
        ts.spot = float(form.get('spot'))
        ts.strike_rate = float(form.get('strike_rate'))
        ts.ko_rate = float(form.get('ko_rate'))
        ts.tenor = form.get('tenor')
        ts.frequency = form.get('frequency')
        ts.gtd = form.get('gtd')
        ts.bank_doc = form.get('bank_doc')
        ts.status = form.get('status')

        ts.save()

        CreateSchedules(ts, db)

        # periods_dict = {}
        # for key, value in form.items():
        #     if "start_date_" in key:
        #         period_num = int(key[-(len(key)-11):])
        #         periods_dict[period_num] = {
        #             "start_date": request.form[f'start_date_{period_num}'],
        #             "end_date": form.get(f'end_date_{period_num}'),
        #             "days": form.get(f'days_{period_num}'),
        #             "received": form.get(f'received_{period_num}'),
        #         }

        # for period_num, entry in periods_dict.items():
        #     schedule = FixingSchedule(
        #         db=db,
        #         ref_num=period_num,
        #         contract_ref=contract_ref,
        #         start_date=entry['start_date'],
        #         end_date=entry['end_date'],
        #         days=entry['days'],
        #         received=entry['received']
        #     )
        #     schedule.save()

        flash(f"{ts.ref_num}: {ts.transaction_type} {ts.reference} has been saved.")
        return redirect(url_for('transactions.home'))
    else:
        ts = {}
        trade_date = str(datetime.datetime.now())[:10]
        start_date = next_day(db, trade_date)


    context = {
        "ts": ts,
        "codes": codes,
        "tenors": tenors,
        "frequencies": frequencies,
        "gtds": gtds,
        "trade_date": trade_date,
        "start_date": start_date
    }
    return render_template('term_sheet/add.html', **context)


@bp.route("/edit/<contract_ref>", methods=["GET", "POST"])
@login_required
def edit(contract_ref):
    db = get_db()
    ts = StockContract(db=db)
    ts.get(ref_num=contract_ref)
    if ts.locked and current_user.role != 'superuser':
        flash("This contract is locked and cannot be edited.")
        return redirect(url_for('transactions.home'))
    ts = StockContract(db=db)

    codes = db.execute("SELECT ref_num, code, stock_name FROM tbl_code;").fetchall()
    tenors = [
        ("1m", "1 month"),
        ("2m", "2 month"),
        ("3m", "3 month"),
        ("4m", "4 month"),
        ("5m", "5 month"),
        ("6m", "6 month"),
        ("7m", "7 month"),
        ("8m", "8 month"),
        ("9m", "9 month"),
        ("10m", "10 month"),
        ("11m", "11 month"),
        ("12m", "12 month"),
        ("13m", "13 month"),
        ("14m", "14 month"),
        ("15m", "15 month"),
    ]
    frequencies = [
        ("monthly", "Monthly"),
        ("bi-monthly", "Bi-Weekly"),
        ("weekly", "Weekly"),
    ]
    gtds = [
        ("No", "No"),
        ("Yes", "Yes"),
        ("1m", "1 month"),
        ("2m", "2 month"),
        ("3m", "3 month"),
        ("4m", "4 month"),
    ]

    if request.method == "POST":
        form = request.form

        ts.ref_num = contract_ref
        ts.reference = form.get('reference')
        ts.bank_ref = int(form.get('bank_ref'))
        ts.code_ref = int(form.get('code_ref'))
        ts.transaction_type = form.get('transaction_type')
        ts.trade_date = form.get('trade_date')
        ts.start_date = form.get('start_date')
        ts.daily_shares = int(form.get('daily_shares'))
        ts.leveraged = form.get('leveraged')
        ts.spot = float(form.get('spot'))
        ts.strike_rate = float(form.get('strike_rate'))
        ts.ko_rate = float(form.get('ko_rate'))
        ts.tenor = form.get('tenor')
        ts.frequency = form.get('frequency')
        ts.gtd = form.get('gtd')
        ts.bank_doc = form.get('bank_doc')
        ts.status = form.get('status')

        ts.save()

        periods_dict = {}
        for key, value in form.items():
            if "start_date_" in key:
                period_num = int(key[-(len(key)-11):])
                periods_dict[period_num] = {
                    "start_date": request.form[f'start_date_{period_num}'],
                    "end_date": form.get(f'end_date_{period_num}'),
                    "days": form.get(f'days_{period_num}'),
                    "received": form.get(f'received_{period_num}'),
                    "gtd": form.get(f'gtd_{period_num}'),
                }

        for period_num, entry in periods_dict.items():
            schedule = FixingSchedule(
                db=db,
                ref_num=period_num,
                contract_ref=contract_ref,
                start_date=entry['start_date'],
                end_date=entry['end_date'],
                days=entry['days'],
                received=entry['received'],
                gtd=entry['gtd']
            )
            schedule.save()

        ts.get_schedules()
        flash(f"{ts.transaction_type} {ts.reference} has been saved.")
    else:
        ts.get(ref_num=contract_ref)
        ts.get_schedules()

    bank_id = db.execute("SELECT bank_id FROM tbl_bank_account WHERE ref_num=?", (ts.bank_ref,)).fetchone()[0]
    return render_template('term_sheet/edit.html', ts=ts, contract_ref=contract_ref,
                           codes=codes, tenors=tenors, frequencies=frequencies,
                           gtds=gtds, bank_id=bank_id)


@bp.route("/<contract_ref>/delete", methods=["GET", "POST"])
@login_required
def delete_contract(contract_ref):
    db = get_db()
    locked = db.execute("SELECT locked FROM tbl_stock_contract WHERE ref_num=?", (contract_ref,)).fetchone()
    if locked and locked['locked'] and current_user.role != 'superuser':
        flash("This contract is locked and cannot be deleted.")
        return redirect(url_for('transactions.home'))
    db.execute("DELETE FROM tbl_stock_contract_period WHERE contract_ref=?;", (contract_ref, ))
    db.execute("DELETE FROM tbl_stock_contract WHERE ref_num=?;", (contract_ref, ))
    db.commit()
    return redirect(url_for('transactions.home'))


@bp.route("/<contract_ref>/<period_ref>/delete", methods=["GET", "POST"])
@login_required
def delete_period(contract_ref, period_ref):
    db = get_db()
    db.execute("DELETE FROM tbl_stock_contract_period WHERE ref_num=?;", (period_ref, ))
    db.commit()
    return redirect(url_for('term_sheet.edit', contract_ref=contract_ref))


@bp.route("/<contract_ref>/set-inactive", methods=["POST"])
@login_required
def set_inactive(contract_ref):
    db = get_db()

    # Check if contract exists and get its current status
    row = db.execute("SELECT status, locked FROM tbl_stock_contract WHERE ref_num=?", (contract_ref,)).fetchone()

    if not row:
        return jsonify({"success": False, "message": "Contract not found"}), 404

    if row['locked'] and current_user.role != 'superuser':
        return jsonify({"success": False, "message": "Contract is locked and cannot be modified"}), 403

    if row['status'] != 'KO':
        return jsonify({"success": False, "message": "Only contracts with KO status can be set to inactive"}), 400

    # Update status to inactive
    db.execute("UPDATE tbl_stock_contract SET status='inactive' WHERE ref_num=?", (contract_ref,))
    db.commit()

    return jsonify({"success": True, "message": "Contract status updated to inactive"})


@bp.route("/<bank_id>/<transaction_type>/<code>", methods=["GET", "POST"])
@login_required
def term_sheet_summary(bank_id, transaction_type, code):
    db = get_db()
    bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account WHERE bank_id=?", (bank_id,)).fetchone()[0]
    sql = """
        SELECT
            tbl_stock_contract.ref_num,
            tbl_stock_contract.reference,
            tbl_stock_contract.trade_date,
            round((tbl_stock_contract.spot * tbl_stock_contract.strike_rate / 100), 4) As strike,
            tbl_stock_contract.bank_doc
        FROM tbl_stock_contract
        INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_stock_contract.bank_ref
        INNER JOIN tbl_code ON tbl_code.ref_num = tbl_stock_contract.code_ref
        WHERE tbl_stock_contract.bank_ref = ?
            AND tbl_code.code = ?
            AND tbl_stock_contract.transaction_type = ?
        ORDER BY tbl_stock_contract.trade_date DESC
    """

    _dict = {
        x['ref_num']: {
            'ref_num': x['ref_num'],
            'trade_date': x['trade_date'],
            'reference': x['reference'],
            'strike': x['strike'],
            'bank_doc': x['bank_doc']
        } for x in db.execute(sql, (bank_ref, code, transaction_type))
    }

    return jsonify(_dict)


def incrementer(data):
    if not data:
        return 1

    if type(data) is int:
        return data + 1

    if data.isdigit():
        return str(int(data) + 1).rjust(len(data), '0')

    # Upon passing this line the data passed is alphanumeric combination
    reversed_data = data[::-1]
    reversed_number = ""
    for i in reversed_data:
        if i.isdigit():
            reversed_number += i
        else:
            break
    proper_number = reversed_number[::-1]

    if proper_number:
        return data[:len(data) - len(proper_number)] + str(int(proper_number) + 1).rjust(
            len(proper_number), '0')
    else:
        return data + "1"


def next_reference(db, bank_ref, code_ref, transaction_type):
    sql = f"SELECT reference " \
          "FROM tbl_stock_contract " \
          f"WHERE bank_ref = {bank_ref} " \
          f"  AND code_ref = {code_ref} " \
          f"  AND transaction_type = '{transaction_type}' " \
          "ORDER BY ref_num DESC"
    on_record = db.execute(sql).fetchall()
    if on_record:
        last_reference = on_record[0][0]
        reference = incrementer(last_reference)
    else:
        sql = f"SELECT stock_name FROM tbl_code WHERE ref_num={code_ref}"
        stock_name = db.execute(sql).fetchone()[0]
        reference = f"{stock_name} - 1"

    return reference


@bp.route("/<contract_ref>/add-line", methods=["GET", "POST"])
@login_required
def add_line(contract_ref):
    db = get_db()

    sql = "INSERT INTO tbl_stock_contract_period " \
          "(contract_ref, end_date, start_date, days, received, gtd) " \
          "VALUES (?, '1900-01-01', '1900-01-01', 20, '', 'No');"

    db.execute(sql, (contract_ref,))
    db.commit()

    return redirect(url_for("term_sheet.edit", contract_ref=contract_ref))
