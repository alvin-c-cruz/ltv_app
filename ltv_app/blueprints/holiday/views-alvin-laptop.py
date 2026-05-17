from flask import Blueprint, render_template, request, flash
from datetime import date
from .models import Holiday

from .. database import get_db
from .. auth import login_required

bp = Blueprint('holiday', __name__, template_folder="pages", url_prefix="/holiday")


@bp.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == "POST":
        date_from = request.form['date_from']
        date_to = request.form['date_to']
    else:
        today = date.today()
        date_from = date(today.year, 1, 1)
        date_to = date(today.year, 12, 31)
        
    date_range = {
        "date_from": date_from,
        "date_to": date_to,
    }
    holidays = Holiday(db=get_db())

    return render_template('holiday/home.html', date_range=date_range,
                           holidays=holidays.list_holidays(date_from, date_to))


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    db = get_db()
    ccys = db.execute("SELECT * FROM tbl_currency ORDER by priority;")
    if request.method == "POST":
        holiday = Holiday(
            db=db,
            ccy_ref=int(request.form['ccy_ref']),
            holi_date=request.form['holi_date']
        )
        holiday.save()
        
        flash("Saved: " + holiday.holi_date)

    return render_template('holiday/add.html', ccys=ccys)

