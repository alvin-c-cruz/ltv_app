from flask import Blueprint, render_template, request, flash
from datetime import datetime
import pandas as pd
from pandas.errors import EmptyDataError

from .. auth import login_required
from .. database import get_db

from .forms import DateForm


bp = Blueprint('stock_price', __name__, template_folder="pages", url_prefix="/stock-price")


@bp.route("/", methods=["POST", "GET"])
@login_required
def home():
    if request.method == "POST":
        csv_files = request.files.getlist("file[]")
        try:
            upload_yahoo_csv(csv_files)
        except EmptyDataError:
            flash("No file to upload", category="errors")

    context = {}

    return render_template("stock_price/home.html", **context)


@bp.route("/view", methods=["GET", "POST"])
@login_required
def view():
    """View stock closing prices for a specific date range"""
    from datetime import timedelta
    db = get_db()

    # Get the selected date from form or default to today
    if request.method == "POST":
        trade_date = request.form.get("trade_date")
    else:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    # Get last 10 trading days to show last week and this week
    available_dates = db.execute(
        "SELECT DISTINCT trade_date FROM tbl_stock_price ORDER BY trade_date DESC LIMIT 10"
    ).fetchall()

    date_list = [row['trade_date'] for row in available_dates]
    date_list.reverse()  # Show oldest to newest (left to right)

    # Get all stock codes
    all_stocks = db.execute("""
        SELECT DISTINCT c.code, c.stock_name, curr.ccy_id
        FROM tbl_code c
        INNER JOIN tbl_currency curr ON curr.ref_num = c.ccy_ref
        WHERE c.ref_num IN (SELECT DISTINCT code_ref FROM tbl_stock_price)
        ORDER BY c.code
    """).fetchall()

    # Build a dictionary of prices: {code: {date: price}}
    price_data = {}
    for stock in all_stocks:
        code = stock['code']
        price_data[code] = {
            'stock_name': stock['stock_name'],
            'currency': stock['ccy_id'],
            'prices': {}
        }

    # Fetch all prices for the date range
    if date_list:
        placeholders = ','.join(['?' for _ in date_list])
        sql = f"""
            SELECT c.code, p.trade_date, p.closing_price
            FROM tbl_stock_price p
            INNER JOIN tbl_code c ON c.ref_num = p.code_ref
            WHERE p.trade_date IN ({placeholders})
        """
        prices = db.execute(sql, date_list).fetchall()

        for price in prices:
            code = price['code']
            if code in price_data:
                price_data[code]['prices'][price['trade_date']] = price['closing_price']

    context = {
        "price_data": price_data,
        "date_list": date_list,
        "trade_date": trade_date,
    }

    return render_template("stock_price/view.html", **context)


def upload_yahoo_csv(csv_files):
    db = get_db()
    data = []
    for file in csv_files:
        df = pd.read_csv(file)
        df.drop(["Trade Date", "Purchase Price", "Quantity", "Commission", "High Limit", "Low Limit", "Comment"],
                axis=1,
                inplace=True)

        # Convert string columns to numeric, replacing errors with NaN
        df["Current Price"] = pd.to_numeric(df["Current Price"], errors='coerce')
        df["Change"] = pd.to_numeric(df["Change"], errors='coerce')

        df["Prev Close"] = df["Current Price"] - df["Change"]
        df["Percent"] = df["Change"] / df["Prev Close"]
        data.append(df)

    for _, row in data[0].iterrows():
        closing_price = row["Current Price"]

        if str(closing_price) == "nan":
            continue

        code_ref = db.execute("SELECT ref_num FROM tbl_code WHERE yahoo_ticker=?;", (row["Symbol"], )).fetchone()[0]

        # Try parsing date in multiple formats
        date_str = row["Date"]
        trade_date = None
        for date_format in ["%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]:
            try:
                trade_date = datetime.strptime(date_str, date_format).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if not trade_date:
            flash(f"Could not parse date: {date_str}", category="errors")
            continue

        # Check if already in database
        if db.execute("SELECT COUNT(*) FROM tbl_stock_price WHERE trade_date=? AND code_ref=?",
                        (trade_date, code_ref)).fetchone()[0]:
            sql = "UPDATE tbl_stock_price SET closing_price = ? WHERE trade_date = ? AND code_ref = ?;"
        else:
            sql = "INSERT INTO tbl_stock_price (closing_price, trade_date, code_ref) VALUES (?, ?, ?);"

        db.execute(sql, (closing_price, trade_date, code_ref))
        db.commit()

