from flask import Blueprint, render_template, request, flash, jsonify
from datetime import datetime
import io
import pandas as pd
from pandas.errors import EmptyDataError

from .. auth import login_required
from .. database import get_db
from ... tz import ph_today

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
        trade_date = str(ph_today())

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


@bp.route("/api/upload", methods=["POST"])
@login_required
def api_upload():
    """Programmatic Yahoo-CSV upload — same processing as the home() form, but
    callable over HTTP (so the daily-closing price upload can be scripted instead
    of a manual browser file-pick).

    Auth: standard session — log in via POST /login first and reuse the cookie.
    Body (either form):
      - multipart/form-data with the CSV as any file field (e.g. requests
        `files={"file": open("portfolio.csv", "rb")}`), or
      - the raw CSV bytes as the request body (Content-Type text/csv).
    Returns JSON: {ok, inserted, updated, skipped, skipped_detail}.
    """
    csv_files = list(request.files.values())
    if not csv_files and request.data:
        buf = io.BytesIO(request.data)
        buf.name = "upload.csv"
        csv_files = [buf]
    if not csv_files:
        return jsonify(ok=False,
                       error="No CSV provided: send a multipart file field or a raw CSV body."), 400
    try:
        summary = upload_yahoo_csv_api(csv_files)
    except EmptyDataError:
        return jsonify(ok=False, error="Empty CSV file."), 400
    except KeyError as exc:
        return jsonify(ok=False, error=f"CSV missing expected column: {exc}"), 400
    except Exception as exc:  # noqa: BLE001 - surface any parse/DB error as JSON
        return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return jsonify(ok=True, **summary)


def upload_yahoo_csv_api(csv_files):
    """Yahoo-CSV -> tbl_stock_price upsert, mirroring upload_yahoo_csv() exactly
    (same column drops, Prev-Close/Percent derivation, and INSERT/UPDATE keyed on
    trade_date + code_ref) but returning counts and *skipping* — rather than
    crashing on — unknown tickers, missing prices, and unparseable dates, so the
    API caller gets a clean summary."""
    db = get_db()
    inserted = updated = skipped = 0
    skipped_detail = []
    for file in csv_files:
        df = pd.read_csv(file)
        df.drop(["Trade Date", "Purchase Price", "Quantity", "Commission",
                 "High Limit", "Low Limit", "Comment"],
                axis=1, inplace=True)

        df["Current Price"] = pd.to_numeric(df["Current Price"], errors="coerce")
        df["Change"] = pd.to_numeric(df["Change"], errors="coerce")
        df["Prev Close"] = df["Current Price"] - df["Change"]
        df["Percent"] = df["Change"] / df["Prev Close"]

        for _, row in df.iterrows():
            symbol = row.get("Symbol")
            closing_price = row["Current Price"]
            if str(closing_price) == "nan":
                skipped += 1
                skipped_detail.append({"symbol": symbol, "reason": "no price"})
                continue

            code = db.execute("SELECT ref_num FROM tbl_code WHERE yahoo_ticker=?;",
                              (symbol,)).fetchone()
            if not code:
                skipped += 1
                skipped_detail.append({"symbol": symbol, "reason": "ticker not in tbl_code"})
                continue
            code_ref = code[0]

            trade_date = None
            for date_format in ["%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]:
                try:
                    trade_date = datetime.strptime(str(row["Date"]), date_format).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue
            if not trade_date:
                skipped += 1
                skipped_detail.append({"symbol": symbol, "reason": f"unparseable date {row['Date']}"})
                continue

            if db.execute("SELECT COUNT(*) FROM tbl_stock_price WHERE trade_date=? AND code_ref=?",
                          (trade_date, code_ref)).fetchone()[0]:
                db.execute("UPDATE tbl_stock_price SET closing_price = ? WHERE trade_date = ? AND code_ref = ?;",
                           (float(closing_price), trade_date, code_ref))
                updated += 1
            else:
                db.execute("INSERT INTO tbl_stock_price (closing_price, trade_date, code_ref) VALUES (?, ?, ?);",
                           (float(closing_price), trade_date, code_ref))
                inserted += 1
            db.commit()

    return {"inserted": inserted, "updated": updated, "skipped": skipped,
            "skipped_detail": skipped_detail[:60]}

