"""Verification that a missing record 404s instead of raising a 500.

Nine routes across four blueprints consumed a lookup result without checking
it, so a nonexistent id produced "TypeError: 'NoneType' object is not
subscriptable" -> HTTP 500.

Root cause for the Model-backed ones: Model.get() returned None whether or not
the row existed, and set every field to None on a miss, so callers could not
tell "found" from "absent" and blew up later on a None field. get() now returns
a bool and callers check it. The bank blueprint uses raw SQL and gets explicit
`is None` guards instead.

Every case is checked BOTH ways -- a bad id must 404 AND a real id must still
return 200. The positive controls are the point: a guard that 404s everything
would pass a negative-only test.

Real ids are read from the live DB at runtime so the controls cannot rot.
Read-only: every probe is a GET, every query a SELECT.

Run: server/.venv/Scripts/python.exe scripts/verify_missing_record_404.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db

app = create_app(test_config={"LOGIN_DISABLED": True})
app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")

GHOST_ID = 999999
GHOST_BANK = "ZZNOPE"

with app.app_context():
    db = get_db()
    contract = db.execute(
        "SELECT ref_num FROM tbl_stock_contract WHERE status != 'inactive' LIMIT 1").fetchone()
    txn = db.execute("SELECT ref_num FROM tbl_transaction LIMIT 1").fetchone()
    div = db.execute("SELECT ref_num FROM tbl_cash_dividends LIMIT 1").fetchone()
    bank_code = db.execute(
        "SELECT b.bank_id, s.code FROM tbl_transaction t "
        "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code s ON s.ref_num = t.code_ref LIMIT 1").fetchone()

missing = [n for n, v in [("stock_contract", contract), ("transaction", txn),
                          ("cash_dividend", div), ("bank/code pair", bank_code)] if v is None]
if missing:
    print("FAIL: no sample rows for:", ", ".join(missing))
    sys.exit(1)

BID, CODE = bank_code["bank_id"], bank_code["code"]

# (path, expected, label)
CASES = [
    # --- bank: raw-SQL bank_id/code lookups
    (f"/bank/{GHOST_BANK}",                    404, "bank.account_position, bad bank_id"),
    (f"/bank/{GHOST_BANK}/{CODE}",             404, "bank.transaction_list, bad bank_id"),
    (f"/bank/{GHOST_BANK}/{CODE}/short",       404, "bank.short_transaction_list, bad bank_id"),
    (f"/bank/{GHOST_BANK}/{CODE}/download",    404, "bank.download_transactions, bad bank_id"),
    (f"/bank/{BID}/ZZZZ",                      404, "bank.transaction_list, bad code"),
    (f"/bank/{BID}",                           200, "control: real bank_id"),
    (f"/bank/{BID}/{CODE}",                    200, "control: real bank_id + code"),
    (f"/bank/{BID}/{CODE}/short",              200, "control: real short list"),
    # --- term_sheet: Model.get() miss
    (f"/term-sheet/edit/{GHOST_ID}",           404, "term_sheet.edit, missing contract"),
    (f"/term-sheet/{GHOST_ID}/view",           404, "term_sheet.view, missing contract"),
    (f"/term-sheet/edit/{contract['ref_num']}", 200, "control: real contract edit"),
    (f"/term-sheet/{contract['ref_num']}/view", 200, "control: real contract view"),
    # --- transactions: Model.get() miss
    (f"/trades/{GHOST_ID}/edit",               404, "transactions.edit, missing txn"),
    (f"/trades/{GHOST_ID}/view",               404, "transactions.view, missing txn"),
    (f"/trades/{txn['ref_num']}/view",         200, "control: real transaction view"),
    # --- dividends: Model.get() miss
    (f"/dividends/edit/{GHOST_ID}",            404, "dividends.edit, missing dividend"),
    (f"/dividends/edit/{div['ref_num']}",      200, "control: real dividend edit"),
]

client = app.test_client()
failures = []

for path, expected, label in CASES:
    status = client.get(path).status_code
    ok = status == expected
    print(f"{'ok ' if ok else 'FAIL'}  GET {path:36} -> {status:3} (want {expected})  {label}")
    if not ok:
        failures.append(f"{path} returned {status}, expected {expected} -- {label}")

if failures:
    print()
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("\nPASS")
