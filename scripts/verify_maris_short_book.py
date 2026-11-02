"""Regression harness: Marissa's three /maris/ downloads carry the Short Book's trades.

Sell (Short) and Buy (Pay Short) live in tbl_transaction_short, and all three downloads read
only tbl_transaction, so no short trade reached her files (BUGS.md 2026-11-02). Return
Shares / Borrow Shares are booked in both tables and must not print twice. On a copy of the
database:
  M1 each date with a short trade: the daily file holds exactly that date's short trades;
  M2 each month with a short trade: the range file holds exactly that month's short trades;
  M3 ... and the posting file does;
  M4 the range file holds Return/Borrow Shares exactly as often as tbl_transaction does;
  M5 the range file's other rows are tbl_transaction's rows, one for one.
Trades are compared as (account, stock, quantity) multisets. No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_maris_short_book.py
"""
import io
import os
import shutil
import sys
import tempfile
from calendar import monthrange
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.marissa_orders.extensions import (
    download_daily_transactions, download_posting, download_transaction_range)

SHORT_TYPES = ("Sell (Short)", "Buy (Pay Short)")
BORROW_RETURN = ("Return Shares", "Borrow Shares")
DATES_TO_CHECK = 30
MONTHS_TO_CHECK = 6

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _code(value):
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _qty(value):
    return round(float(value), 4)


def _db_trades(db, table, types, start, end, key):
    marks = ",".join("?" * len(types))
    rows = db.execute(
        f"SELECT b.bank_id, b.bank_name, c.code, t.quantity FROM {table} t "
        "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code c ON c.ref_num = t.code_ref "
        f"WHERE t.transaction_type IN ({marks}) AND t.trade_date >= ? AND t.trade_date <= ?",
        (*types, start, end)).fetchall()
    return Counter((r[key], _code(r["code"]), _qty(r["quantity"])) for r in rows)


def _sheet_trades(output, types):
    """(account, code, quantity) of the rows whose Transaction column is one of types.
    Daily and range files: B account name, C type, D code, E quantity."""
    ws = load_workbook(io.BytesIO(output.getvalue())).active
    return Counter((r[1], _code(r[3]), _qty(r[4])) for r in ws.iter_rows(min_row=2, values_only=True)
                   if r[2] in types)


def _posting_trades(output):
    """Posting file: one sheet per <bank_id>-<ccy>; C type, D code, F quantity."""
    found = Counter()
    for ws in load_workbook(io.BytesIO(output.getvalue())).worksheets:
        bank_id = ws.title.rsplit("-", 1)[0]
        for r in ws.iter_rows(min_row=2, values_only=True):
            if len(r) > 5 and r[2] in SHORT_TYPES:
                found[(bank_id, _code(r[3]), _qty(r[5]))] += 1
    return found


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    dates = [r[0] for r in db.execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction_short "
        "WHERE transaction_type IN (?, ?) ORDER BY 1 DESC LIMIT ?", (*SHORT_TYPES, DATES_TO_CHECK))]
    months = sorted({d[:7] for d in dates}, reverse=True)[:MONTHS_TO_CHECK]
    bad = Counter()
    for d in dates:
        out, _ = download_daily_transactions(db, d)
        if _sheet_trades(out, SHORT_TYPES) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, d, d, "bank_name"):
            bad["M1"] += 1
    for m in months:
        year, month = int(m[:4]), int(m[5:7])
        start, end = f"{m}-01", f"{m}-{monthrange(year, month)[1]:02d}"
        out, _ = download_transaction_range(db, start, end)
        if _sheet_trades(out, SHORT_TYPES) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, start, end, "bank_name"):
            bad["M2"] += 1
        if _sheet_trades(out, BORROW_RETURN) != _db_trades(db, "tbl_transaction", BORROW_RETURN, start, end, "bank_name"):
            bad["M4"] += 1
        long_types = [r[0] for r in db.execute(
            "SELECT DISTINCT transaction_type FROM tbl_transaction WHERE transaction_type NOT IN (?, ?)",
            BORROW_RETURN)]
        if _sheet_trades(out, long_types) != _db_trades(db, "tbl_transaction", long_types, start, end, "bank_name"):
            bad["M5"] += 1
        out, _ = download_posting(db, month, year)
        if _posting_trades(out) != _db_trades(db, "tbl_transaction_short", SHORT_TYPES, start, end, "bank_id"):
            bad["M3"] += 1

_case(f"M0 short-trade dates checked ({len(dates)}) and months ({len(months)})", bool(dates and months), True)
for key, label in (("M1", "daily files missing or adding short trades"),
                   ("M2", "range files missing or adding short trades"),
                   ("M3", "posting files missing or adding short trades"),
                   ("M4", "range files printing Return/Borrow Shares twice"),
                   ("M5", "range files whose long-book rows changed")):
    _case(f"{key} {label}", bad[key], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
