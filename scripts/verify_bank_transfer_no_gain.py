"""Regression harness: no gain or loss on a transfer, on /bank/<id>/<code> or in its download.

A transfer moves shares and cost between Alvin's own accounts; it realises nothing. Alvin,
30 Oct 2026: "there shouldn't be any gain or loss in transfers" (BUGS.md 2026-11-02). The
transaction list treated every qty < 0 row on a long balance as a sale. On a copy of the
database, for every (account, stock, year) holding a transfer:
  T1 every Transfer-In / Transfer-Out row carries a gain/loss of 0;
  T2 every sale's gain is still proceeds - charges - (previous running average x shares);
  T3 in the download, transfer rows have no Gain/Loss formula and sales keep theirs;
  T0 transfers and sales were found.
No figure is printed.

Run: ../venv/Scripts/python.exe scripts/verify_bank_transfer_no_gain.py
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.bank.views import _compute_transactions

TRANSFERS = ("Transfer-In", "Transfer-Out")
DOWNLOADS_TO_CHECK = 25
DATA_ROW = 7          # header row 5, Balance Forwarded row 6

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


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    transfer_refs = {r[0] for r in db.execute(
        "SELECT ref_num FROM tbl_transaction WHERE transaction_type IN (?, ?)", TRANSFERS)}
    combos = db.execute(
        "SELECT DISTINCT t.bank_ref, t.code_ref, substr(t.trade_date, 1, 4) AS year, b.bank_id, c.code "
        "FROM tbl_transaction t INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code c ON c.ref_num = t.code_ref "
        "WHERE t.transaction_type IN (?, ?) ORDER BY year DESC", TRANSFERS).fetchall()

    transfers_seen = sales_seen = 0
    wrong = {"T1": 0, "T2": 0, "T3": 0}
    for i, combo in enumerate(combos):
        date_from, date_to = f"{combo['year']}-01-01", f"{combo['year']}-12-31"
        start_qty, start_avg, rows = _compute_transactions(
            db, combo["bank_ref"], combo["code_ref"], date_from, date_to)
        prev_avg, prev_bal = start_avg, start_qty
        for row in rows:
            if row["ref_num"] in transfer_refs:
                transfers_seen += 1
                if abs(row["gain_loss"]) > 1e-9:
                    wrong["T1"] += 1
            elif row["quantity"] < 0 and prev_bal > 0:
                sales_seen += 1
                q = abs(row["quantity"])
                expected = q * row["price"] - row["charges"] - prev_avg * q
                if abs(row["gain_loss"] - expected) > 1e-6 * max(1.0, abs(expected)):
                    wrong["T2"] += 1
            prev_avg, prev_bal = row["average"], row["balance"]

        if i < DOWNLOADS_TO_CHECK:
            response = client.get(f"/bank/{combo['bank_id']}/{combo['code']}/download"
                                  f"?date_from={date_from}&date_to={date_to}")
            ws = load_workbook(io.BytesIO(response.get_data())).active
            response.close()
            for r, row in enumerate(rows, start=DATA_ROW):
                gl = ws.cell(row=r, column=8).value
                if row["ref_num"] in transfer_refs:
                    if gl not in (None, ""):
                        wrong["T3"] += 1
                elif row["quantity"] < 0 and not (isinstance(gl, str) and gl.startswith("=IF(")):
                    wrong["T3"] += 1

_case(f"T0 transfers ({transfers_seen}) and sales ({sales_seen}) found",
      transfers_seen > 0 and sales_seen > 0, True)
_case("T1 transfer rows with a gain or loss", wrong["T1"], 0)
_case("T2 sales whose gain changed", wrong["T2"], 0)
_case("T3 download rows with the wrong Gain/Loss cell", wrong["T3"], 0)
print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
