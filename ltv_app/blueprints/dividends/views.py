from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, send_file
from datetime import datetime
import os

from ..auth import login_required
from ..database import get_db
from ...tz import ph_today

from .models import CashDividends
from .forms import Form
from .extensions import CreateExcel

bp = Blueprint('dividends', __name__, template_folder="pages", url_prefix="/dividends")


@bp.route("/", methods=["GET"])
@login_required
def home():
    try:
        create_table()
    except:
        pass
    db = get_db()
    today = ph_today()
    start_date = request.args.get('start_date') or f"{today.year}-01-01"
    end_date = request.args.get('end_date') or f"{today.year}-12-31"
    sql = """
    SELECT
        tbl_cash_dividends.ref_num,
        tbl_bank_account.bank_name,
        tbl_code.stock_name,
        tbl_code.code AS stock_code,
        tbl_cash_dividends.nominal,
        tbl_cash_dividends.declaration_date,
        tbl_cash_dividends.ex_date,
        tbl_cash_dividends.record_date,
        tbl_cash_dividends.pay_out,
        tbl_currency.ccy_id AS ccy_code,
        tbl_cash_dividends.dividends_per_share,
        tbl_cash_dividends.tax,
        tbl_cash_dividends.charges,
        tbl_cash_dividends.status
    FROM tbl_cash_dividends
    INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_cash_dividends.bank_id
    INNER JOIN tbl_code ON tbl_code.ref_num = tbl_cash_dividends.stock_id
    INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_cash_dividends.ccy_id
    WHERE tbl_cash_dividends.pay_out >= ? AND tbl_cash_dividends.pay_out <= ?
    ORDER BY tbl_cash_dividends.ref_num desc
    ;
    """
    dividends = db.execute(sql, (start_date, end_date)).fetchall()
    context = {
        "dividends": dividends,
        "start_date": start_date,
        "end_date": end_date,
        "today": str(today),
    }
    return render_template("dividends/home.html", **context)


@bp.route("/export", methods=["GET"])
@login_required
def export():
    db = get_db()
    today = ph_today()
    start_date = request.args.get('start_date') or f"{today.year}-01-01"
    end_date = request.args.get('end_date') or f"{today.year}-12-31"

    excel_file = CreateExcel(
        path=os.path.join(current_app.instance_path, "temp"),
        start_date=start_date,
        end_date=end_date,
        db=db
    )
    return send_file(excel_file.filename, as_attachment=True)


@bp.route("/add", methods=["GET", "POST"])
@login_required
def add():
    db = get_db()
    form = Form()
    select_fields(db, form)

    if request.method == "POST" or form.validate_on_submit():
        dividend = CashDividends(
            db=db,
            bank_id=int(form.bank_id.data),
            stock_id=int(form.stock_id.data),
            declaration_date=_optional_date(form.declaration_date.data),
            ex_date=str(form.ex_date.data)[:10],
            record_date=_optional_date(form.record_date.data),
            pay_out=str(form.pay_out.data)[:10],
            nominal=float(form.nominal.data),
            ccy_id=int(form.ccy_id.data),
            dividends_per_share=float(form.dividends_per_share.data),
            tax=float(form.tax.data),
            charges=float(form.charges.data),
            status=form.status.data
        )
        dividend.save()
        flash("Dividend saved.")
        return redirect(url_for('dividends.home'))

    context = {
        "form": form
    }
    return render_template("dividends/add.html", **context)


@bp.route("/edit/<int:ref_num>", methods=["GET", "POST"])
@login_required
def edit(ref_num):
    db = get_db()
    form = Form()
    dividend = CashDividends(db=db)
    dividend.get(ref_num=ref_num)
    select_fields(db, form)

    if request.method == "POST" or form.validate_on_submit():
        dividend.bank_id = int(form.bank_id.data)
        dividend.stock_id = int(form.stock_id.data)
        dividend.declaration_date = _optional_date(form.declaration_date.data)
        dividend.ex_date = str(form.ex_date.data)[:10]
        dividend.record_date = _optional_date(form.record_date.data)
        dividend.pay_out = str(form.pay_out.data)[:10]
        dividend.nominal = float(form.nominal.data)
        dividend.ccy_id = int(form.ccy_id.data)
        dividend.dividends_per_share = float(form.dividends_per_share.data)
        dividend.tax = float(form.tax.data)
        dividend.charges = float(form.charges.data)
        dividend.status = form.status.data

        dividend.save()
        flash("Dividend saved.")
        return redirect(url_for('dividends.home'))
    else:
        form.bank_id.data = str(dividend.bank_id)
        form.stock_id.data = str(dividend.stock_id)
        form.declaration_date.data = _parse_date(dividend.declaration_date)
        form.ex_date.data = datetime(int(dividend.ex_date[:4]), int(dividend.ex_date[5:7]), int(dividend.ex_date[-2:]))
        form.record_date.data = _parse_date(dividend.record_date)
        form.pay_out.data = datetime(int(dividend.pay_out[:4]), int(dividend.pay_out[5:7]), int(dividend.pay_out[-2:]))
        form.nominal.data = dividend.nominal
        form.ccy_id.data = str(dividend.ccy_id)
        form.dividends_per_share.data = dividend.dividends_per_share
        form.tax.data = dividend.tax
        form.charges.data = dividend.charges
        form.status.data = dividend.status

    context = {
        "form": form,
        "ref_num": ref_num
    }
    return render_template("dividends/edit.html", **context)


@bp.route("/delete/<int:ref_num>")
@login_required
def delete(ref_num):
    db = get_db()
    dividend = CashDividends(db=db)
    dividend.delete(ref_num=ref_num)

    flash("Dividend deleted.")
    return redirect(url_for('dividends.home'))


def _optional_date(value):
    """WTForms DateField -> 'YYYY-MM-DD' string for storage, or None if blank."""
    return str(value)[:10] if value else None


def _parse_date(value):
    """Stored 'YYYY-MM-DD' string -> datetime for populating a DateField, or None."""
    if not value:
        return None
    return datetime(int(value[:4]), int(value[5:7]), int(value[-2:]))


def select_fields(db, form):
    form.bank_id.choices = [("", "")] + [(row['ref_num'], f"{row['bank_id']}: {row['bank_name']}")
                            for row in db.execute(
            "SELECT ref_num, bank_id, bank_name FROM tbl_bank_account ORDER by priority;"
        ).fetchall()]

    form.stock_id.choices = [("", "")] + [(row['ref_num'], f"{row['code']}: {row['stock_name']}")
                            for row in db.execute(
            "SELECT ref_num, code, stock_name FROM tbl_code ORDER by code;"
        ).fetchall()]

    form.ccy_id.choices = [("", "")] + [(row['ref_num'], f"{row['ccy_id']}: {row['ccy_name']}")
                            for row in db.execute(
            "SELECT ref_num, ccy_id, ccy_name FROM tbl_currency ORDER by priority;"
        ).fetchall()]


def create_table():
    db = get_db()
    sql = """
    CREATE TABLE tbl_cash_dividends
        (
        ref_num INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_id INT,
        stock_id INT,
        declaration_date TIMESTAMP,
        ex_date TIMESTAMP,
        record_date TIMESTAMP,
        pay_out TIMESTAMP,
        nominal REAL,
        ccy_id INT,
        dividends_per_share REAL,
        tax REAL,
        charges REAL,
        status TEXT
        )
    ;"""
    db.execute(sql)
