from flask import Blueprint, render_template, request, redirect, url_for

from .. database import get_db
from .. auth import login_required
from ...tz import ph_today

bp = Blueprint('holiday', __name__, template_folder="pages", url_prefix="/holiday")


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    today = ph_today()
    if request.method == "POST":
        date_from = request.form['date_from']
        date_to   = request.form['date_to']
    else:
        date_from = str(today.replace(month=1, day=1))
        date_to   = str(today.replace(month=12, day=31))

    db = get_db()
    rows = db.execute(
        "SELECT c.ccy_id, h.holi_date "
        "FROM tbl_holiday h "
        "INNER JOIN tbl_currency c ON c.ref_num = h.ccy_ref "
        "WHERE h.holi_date >= ? AND h.holi_date <= ? "
        "ORDER BY c.priority, h.holi_date",
        (date_from, date_to)
    ).fetchall()

    grouped = {}
    for row in rows:
        ccy = row['ccy_id']
        if ccy not in grouped:
            grouped[ccy] = []
        d = date.fromisoformat(row['holi_date'])
        grouped[ccy].append({
            'iso':  row['holi_date'],
            'date': f"{d.day} {d.strftime('%b')} {d.year}",
            'day':  d.strftime('%A'),
        })

    return render_template('holiday/home.html',
                           date_from=date_from,
                           date_to=date_to,
                           grouped=grouped)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    db = get_db()
    ccys = db.execute("SELECT * FROM tbl_currency ORDER BY priority;").fetchall()
    if request.method == "POST":
        db.execute(
            "INSERT INTO tbl_holiday (ccy_ref, holi_date) VALUES (?, ?)",
            (int(request.form['ccy_ref']), request.form['holi_date'])
        )
        db.commit()
        return redirect(url_for('holiday.home'))

    return render_template('holiday/add.html', ccys=ccys)
