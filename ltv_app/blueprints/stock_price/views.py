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
    """View stock closing prices for a specific date"""
    db = get_db()

    # Get the selected date from form or default to today
    if request.method == "POST":
        trade_date = request.form.get("trade_date")
    else:
        trade_date = datetime.now().strftime("%Y-%m-%d")

    # Get all stock prices for the selected date
    sql = """
        SELECT
            c.code,
            c.stock_name,
            p.closing_price,
            p.trade_date,
            curr.ccy_id
        FROM tbl_stock_price p
        INNER JOIN tbl_code c ON c.ref_num = p.code_ref
        INNER JOIN tbl_currency curr ON curr.ref_num = c.ccy_ref
        WHERE p.trade_date = ?
        ORDER BY c.code
    """

    stock_prices = db.execute(sql, (trade_date,)).fetchall()

    # Get list of available dates
    available_dates = db.execute(
        "SELECT DISTINCT trade_date FROM tbl_stock_price ORDER BY trade_date DESC LIMIT 30"
    ).fetchall()

    context = {
        "stock_prices": stock_prices,
        "trade_date": trade_date,
        "available_dates": [row['trade_date'] for row in available_dates]
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
        trade_date = datetime.strptime(row["Date"], "%Y/%m/%d").strftime("%Y-%m-%d")

        # Check if already in database
        if db.execute("SELECT COUNT(*) FROM tbl_stock_price WHERE trade_date=? AND code_ref=?",
                        (trade_date, code_ref)).fetchone()[0]:
            sql = "UPDATE tbl_stock_price SET closing_price = ? WHERE trade_date = ? AND code_ref = ?;"
        else:
            sql = "INSERT INTO tbl_stock_price (closing_price, trade_date, code_ref) VALUES (?, ?, ?);"

        db.execute(sql, (closing_price, trade_date, code_ref))
        db.commit()

