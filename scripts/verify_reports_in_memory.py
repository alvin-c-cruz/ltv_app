"""Regression harness: no report download writes a file on the server.

Every report used to save its workbook into instance/temp/ and send that file,
so each one anybody generated stayed on PythonAnywhere -- positions, prices and
bank names, 153 files by 2026-09 (BUGS.md 2026-09-06). Alvin chose on
2026-10-27 to build them in memory instead (ltv_app/workbook_download.py), as
/ltv-stocks/ and /gain-loss/ already did.

For every report download, with parameters taken from the newest trade date that
has a Trades Done (a date of fixings alone has none):
  1. it answers 200 with an .xlsx body;
  2. it is offered under the same file name as before (Content-Disposition);
  3. nothing in instance/temp/ is created or modified.
The cell content was compared before and after the change, on the 22 Oct 2026
snapshot, and was identical for all of them; that comparison needs the old code,
so it is not repeated here. No figure is printed.

Run: server/.venv/Scripts/python.exe scripts/verify_reports_in_memory.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.transactions.extensions import download_trades_done_with_gain_loss as trades_done

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")

trades_done.fetch_hkd_rate = lambda ccy: (6.1234, "test feed")
app = create_app({"DATABASE": DB_PATH, "LOGIN_DISABLED": True, "WTF_CSRF_ENABLED": False})
client = app.test_client()
temp = os.path.join(app.instance_path, "temp")
with app.app_context():
    dates = [r[0] for r in get_db().execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction ORDER BY 1 DESC LIMIT 30")]
with app.app_context():
    from ltv_app.blueprints.transactions.extensions import TransactionSummary
    day = next(d for d in dates if not TransactionSummary(get_db(), d).is_empty())
month, year = day[:7], day[:4]
first = f"{month}-01"

# (label, method, url, form, the file name it is offered under)
REPORTS = [
    ("fixings", "GET", f"/fixings/generate/{day}", None, f"{day} Fixings.xlsx"),
    ("notebook", "GET", f"/notebook/generate/{day}", None, f"{day} notebook.xlsx"),
    ("trades done", "GET", f"/trades/download_with_gain_loss/{day}", None,
     f"{day} Trades Done with gain loss.xlsx"),
    ("block / unblock", "POST", "/block-unblock/", {}, "blocked_shares.xlsx"),
    ("cash margin", "GET", f"/cash-margin/download/HKD/{month}", None, f"cash_margin_HKD_{month}.xlsx"),
    ("dividends", "GET", f"/dividends/export?start_date={year}-01-01&end_date={year}-12-31", None,
     f"{year}-01-01_to_{year}-12-31 dividends.xlsx"),
    ("hkd margin", "GET", "/hkd-margin/", None, "hkd_margin.xlsx"),
    ("stock posting", "POST", "/maris/", {"cmd_button": "Download Stock Posting",
                                          "posting_month": str(int(day[5:7])), "posting_year": year},
     f"stock_posting_{year}_{day[5:7]}.xlsx"),
    ("daily transactions", "POST", "/maris/", {"cmd_button": "Download Daily Transaction", "trade_date": day},
     f"daily_transactions_{day}.xlsx"),
    ("transaction range", "POST", "/maris/", {"cmd_button": "Download Transaction Range",
                                              "range_start": first, "range_end": day},
     f"transaction_range_{first}_{day}.xlsx"),
    ("portfolio", "POST", "/portfolio/", {"report_date": day}, f"{day} portfolio.xlsx"),
    ("gain / loss", "POST", "/gain-loss/", {"date_from": first, "date_to": day, "bank_ref": "0", "code_ref": "0"},
     f"{first}-to-{day}-gain_loss.xlsx"),
]


def _files():
    return {f: os.path.getmtime(os.path.join(temp, f)) for f in os.listdir(temp)} if os.path.isdir(temp) else {}


ok = True
for label, method, url, form, name in REPORTS:
    before = _files()
    r = client.get(url) if method == "GET" else client.post(url, data=form)
    body = r.get_data()
    disposition = r.headers.get("Content-Disposition", "")
    r.close()
    after = _files()
    written = [f for f in after if before.get(f) != after[f]]
    checks = [
        ("200 with a workbook", r.status_code == 200 and body[:2] == b"PK"),
        ("same file name", f'filename="{name}"' in disposition or f"filename={name}" in disposition),
        ("nothing written to instance/temp", not written),
    ]
    for what, passed in checks:
        print(f"  {label}: {what}: {'PASS' if passed else 'FAIL'}")
        ok &= passed

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
