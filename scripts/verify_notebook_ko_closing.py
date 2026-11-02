"""Regression harness: a notebook KO block prints the knock-out day's close and its date.

Alvin types both under the red "Closing" label of every KO block (BUGS.md 2026-11-02). They
are the stock's close on its last trading day before the notebook's date, which is
tbl_stock_price's close for that day. KO rows carry no fixing_date, so the day comes from
the calendar. For the newest dates with a KO trade, generated through the route on a copy
of the database:
  K1 a block whose close is held shows that close under the label;
  K2 ... and that day as the date under it;
  K3 a block whose close is not held leaves both cells blank;
  K0 enough blocks were seen, at least one with a close held.
The expected day is worked out here from tbl_holiday and weekends, not with WorkingDay.
No figure is printed.

Run: ..\venv\Scripts\python.exe scripts\verify_notebook_ko_closing.py
"""
import io
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app

DATES_TO_CHECK = 30
FIRST_ACCOUNT_ROW = 24
TITLE_CODE = re.compile(r"\(([^()]*)\)\s*$")

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _previous_trading_day(db, ccy_id, d):
    holidays = {str(r[0])[:10] for r in db.execute(
        "SELECT h.holi_date FROM tbl_holiday h INNER JOIN tbl_currency c ON c.ref_num = h.ccy_ref "
        "WHERE c.ccy_id = ?", (ccy_id,))}
    d -= timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d -= timedelta(days=1)
    return d


def _expected(db, code, notebook_date):
    row = db.execute(
        "SELECT tbl_code.ref_num, tbl_currency.ccy_id FROM tbl_code "
        "INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref WHERE tbl_code.code = ?",
        (code,)).fetchone()
    day = _previous_trading_day(db, row["ccy_id"], notebook_date)
    price = db.execute(
        "SELECT closing_price FROM tbl_stock_price WHERE code_ref = ? AND substr(trade_date, 1, 10) = ?",
        (row["ref_num"], day.isoformat())).fetchone()
    return day, (price[0] if price else None)


def _block_code(ws, label_row):
    """The stock of a Closing label: the code in the nearest numbered line title above it."""
    for r in range(label_row, FIRST_ACCOUNT_ROW - 1, -1):
        title = ws[f"C{r}"].value
        if isinstance(ws[f"B{r}"].value, int) and isinstance(title, str) and TITLE_CODE.search(title):
            return TITLE_CODE.search(title).group(1)
    return None


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    dates = [r[0] for r in db.execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction "
        "WHERE transaction_type LIKE '%KO%' ORDER BY 1 DESC LIMIT ?", (DATES_TO_CHECK,))]
    seen, held = 0, 0
    wrong = {"K1": 0, "K2": 0, "K3": 0}
    for d in dates:
        response = client.get(f"/notebook/generate/{d}")
        data = response.get_data()
        response.close()
        if response.status_code != 200:
            continue
        ws = load_workbook(io.BytesIO(data))["notebook"]
        for r in range(FIRST_ACCOUNT_ROW, ws.max_row + 1):
            if ws[f"O{r}"].value != "Closing":
                continue
            code = _block_code(ws, r)
            if code is None:
                continue
            seen += 1
            day, price = _expected(db, code, date.fromisoformat(d))
            shown_price, shown_day = ws[f"O{r + 1}"].value, ws[f"O{r + 2}"].value
            if price is None:
                if shown_price is not None or shown_day is not None:
                    wrong["K3"] += 1
                continue
            held += 1
            if shown_price is None or abs(float(shown_price) - float(price)) > 1e-9:
                wrong["K1"] += 1
            if not isinstance(shown_day, datetime) or shown_day.date() != day:
                wrong["K2"] += 1

_case(f"K0 KO blocks seen ({seen}), some with a close held", seen >= 5 and held >= 1, True)
_case("K1 KO blocks without the knock-out day's close", wrong["K1"], 0)
_case("K2 KO blocks without the knock-out day's date", wrong["K2"], 0)
_case("K3 KO blocks with no close held that are not blank", wrong["K3"], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
