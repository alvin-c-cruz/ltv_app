"""Verification that an unknown bank_id 404s instead of raising a 500.

/term-sheet/<bank_id> and /term-sheet/<bank_id>/<transaction_type>/<code> both
look up tbl_bank_account by bank_id and then immediately subscript the result.
When the lookup misses, fetchone() returns None and the unpack/index raises
TypeError -> HTTP 500.

This is not hypothetical: the PythonAnywhere error log shows two real hits,
both plausible human confusions rather than probing --

    2026-08-06  Exception on /term-sheet/12099112 [GET]   (SHK1's broker
                                                           account number)
    2026-08-12  Exception on /term-sheet/8 [GET]          (SHK's ref_num;
                                                           its bank_id is 'SHK')

bank_id is a string code ('DBPe', 'SHK', 'MST1'), so unlike ref_num this route
cannot be fixed with an <int:...> converter -- it needs an explicit guard.

Read-only: every probe is a GET and every query a SELECT. Uses LOGIN_DISABLED
so the probes reach the view instead of redirecting to /login.

Run: server/.venv/Scripts/python.exe scripts/verify_bank_id_404.py
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

# Derive a genuinely valid summary URL from the data, so the positive control
# can never rot as contracts change.
with app.app_context():
    db = get_db()
    row = db.execute(
        "SELECT b.bank_id, c.transaction_type, s.code "
        "FROM tbl_stock_contract c "
        "INNER JOIN tbl_bank_account b ON b.ref_num = c.bank_ref "
        "INNER JOIN tbl_code s ON s.ref_num = c.code_ref "
        "WHERE c.status != 'inactive' LIMIT 1"
    ).fetchone()
    valid_summary = (f"/term-sheet/{row['bank_id']}/{row['transaction_type']}/{row['code']}"
                     if row else None)

client = app.test_client()
failures = []

# (path, expected_status, why)
PROBES = [
    ("/term-sheet/8",              404, "ref_num mistaken for bank_id (real 2026-08-12 hit)"),
    ("/term-sheet/12099112",       404, "broker account number (real 2026-08-06 hit)"),
    ("/term-sheet/NOPE",           404, "plainly unknown code"),
    ("/term-sheet/8/DECU/0175",    404, "same miss on the summary route"),
    ("/term-sheet/DBPe",           200, "positive control -- a real bank_id must still work"),
]
if valid_summary:
    PROBES.append((valid_summary, 200, "positive control -- a real summary URL must still work"))

for path, expected, why in PROBES:
    status = client.get(path).status_code
    verdict = "ok" if status == expected else f"FAIL (wanted {expected})"
    print(f"GET {path:34} -> {status:3}  {verdict}   [{why}]")
    if status != expected:
        failures.append(f"{path} returned {status}, expected {expected} -- {why}")

if failures:
    print()
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("\nPASS")
