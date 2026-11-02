"""Regression harness: the Gain Loss workbook's SUMMARY carries every account, and its totals
and rates hang together.

The template's SUMMARY had no SHK No. 2 row and no Nomura section, so their gains never
reached the Total. Alvin widened it by hand each time, and that is where his 30 Oct file went
wrong (BUGS.md 2026-11-02). Generated through POST /gain-loss/ on a copy of the database, for
the newest month and the year to date (all banks, all stocks). Formulas stay unevaluated
(openpyxl), so this checks their structure:
  G1 every visible account sheet's bank has a SUMMARY row (column N);
  G2 every active account has a SUMMARY row;
  G3 each SUB-Total sums exactly its group's account rows, and the Total sums every SUB-Total;
  G4 each account row reads its own N and the currency key row;
  G7 no sheet links to a fixed SUMMARY account row (=SUMMARY!C31); they look up column N.
No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_gain_loss_workbook.py
"""
import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app

CCYS = ("HKD", "JPY", "AUD", "USD", "SGD")
KEY_CURRENCIES = ["AUD", "HKD", "JPY", "USD", "SGD"]
NET_COLS = "BCDEF"
FIXED_LINK = re.compile(r"^=SUMMARY!\$?([A-Z]{1,2})\$?(\d+)$")

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


def _generate(date_from, date_to):
    response = client.post("/gain-loss/", data={"date_from": date_from, "date_to": date_to,
                                                "bank_ref": 0, "code_ref": 0})
    data = response.get_data()
    response.close()
    return load_workbook(io.BytesIO(data))


def _check(wb, active_ids, tag):
    ws = wb["SUMMARY"]
    n_rows = {ws[f"N{r}"].value: r for r in range(9, ws.max_row + 1) if ws[f"N{r}"].value}
    sheets = {name.rpartition("-")[0] for name in wb.sheetnames
              if name.rpartition("-")[2] in CCYS and name.rpartition("-")[0]
              and wb[name].sheet_state == "visible"}
    _case(f"G1 [{tag}] account sheets without a SUMMARY row", sorted(sheets - set(n_rows)), [])
    _case(f"G2 [{tag}] active accounts without a SUMMARY row", sorted(set(active_ids) - set(n_rows)), [])

    subtotals = [r for r in range(9, ws.max_row + 1) if ws[f"A{r}"].value == "SUB-Total"]
    total = next(r for r in range(9, ws.max_row + 1) if ws[f"A{r}"].value == "Total")
    key = next(r for r in range(total, ws.max_row + 1)
               if [ws[f"{c}{r}"].value for c in NET_COLS] == KEY_CURRENCIES)
    bad_sub = 0
    for s in subtotals:
        for c in NET_COLS:
            m = re.fullmatch(rf"=SUM\({c}(\d+):{c}(\d+)\)", str(ws[f"{c}{s}"].value))
            if not m:
                bad_sub += 1
                continue
            first, last = int(m.group(1)), int(m.group(2))
            if last != s - 1 or ws[f"N{first - 1}"].value or not ws[f"A{first - 1}"].value \
                    or not all(ws[f"N{r}"].value for r in range(first, last + 1)):
                bad_sub += 1
    bad_total = sum(1 for c in NET_COLS
                    if sorted(int(x) for x in re.findall(rf"{c}(\d+)", str(ws[f"{c}{total}"].value))) != subtotals)
    _case(f"G3 [{tag}] SUB-Totals or Total summing the wrong rows", bad_sub + bad_total, 0)

    bad_rows = sum(1 for r in n_rows.values() for c in NET_COLS
                   if f"$N{r}&" not in str(ws[f"{c}{r}"].value) or f"{c}${key}" not in str(ws[f"{c}{r}"].value))
    _case(f"G4 [{tag}] account rows not reading their own N and the key row", bad_rows, 0)

    fixed = 0
    for sheet in wb.worksheets:
        if sheet.title == "SUMMARY":
            continue
        for row in sheet.iter_rows():
            for cell in row:
                m = FIXED_LINK.match(str(cell.value)) if isinstance(cell.value, str) else None
                if m and int(m.group(2)) >= 9:
                    fixed += 1
    _case(f"G7 [{tag}] links to a fixed SUMMARY account row", fixed, 0)


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    newest = db.execute("SELECT max(substr(trade_date, 1, 10)) FROM tbl_transaction").fetchone()[0]
    active = [r[0] for r in db.execute("SELECT bank_id FROM tbl_bank_account WHERE is_active = 1")]

for tag, date_from in (("month", newest[:7] + "-01"), ("year", newest[:4] + "-01-01")):
    _check(_generate(date_from, newest), active, tag)

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
