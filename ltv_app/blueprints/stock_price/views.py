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

