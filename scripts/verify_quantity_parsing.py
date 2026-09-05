"""Verification that a quantity typed with a thousands separator is accepted,
and that no form field reaches int()/float() or SQL unparsed.

`-12,345` is the form a share count takes when it is copied out of a broker
statement or Excel. It used to reach `int(request.form["quantity"])` unfiltered
and raise ValueError -> HTTP 500, losing the whole typed form (confirmed live on
PA 2026-09-03). On `review.edit` it was worse than a crash: the raw string went
straight into the UPDATE, and SQLite stores it as TEXT in an INTEGER column,
where `SUM()` reads `-12,345` as -12 -- every balance derived from it silently
wrong, with nothing to notice. See server/BUGS.md (2026-09-04).

Case A pins the coercion itself. Case B drives the real routes through Flask's
test client. Case C is structural -- it asserts no blueprint parses a form value
with a bare `int(...)`/`float(...)` again, which a new view cannot regress
without failing here, and which no amount of fixing today's call sites one by
one would otherwise keep true.

Case B writes, so it runs against a throwaway copy of the database in the
system temp directory, deleted afterwards; the live `instance/LTV Stocks.db` is
opened read-only for one SELECT to pick real ids and never written to.

Run: server/.venv/Scripts/python.exe scripts/verify_quantity_parsing.py
"""
import os
import re
import shutil
import sys
import sqlite3
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.form_fields import FormFields, clean_number

LIVE_DB = os.path.join(SERVER, "instance", "LTV Stocks.db")

_ok = True


def _case(label, actual, expected):
    global _ok
    if actual == expected:
        print(f"  {label}: PASS")
        return True
    print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")
    _ok = False
    return False


# --- Case A: the coercion ----------------------------------------------------
print("A  coercion")
_case("A1 comma thousands separator", clean_number("-12,345"), "-12345")
_case("A2 surrounding whitespace", clean_number("  1 200 "), "1200")
_case("A3 substituted minus sign", clean_number("−500"), "-500")
_case("A4 left alone when unparseable", clean_number("12x4"), "12x4")

f = FormFields({"quantity": "-12,345", "price": "10.25"})
_case("A5 quantity parses to an int", f.quantity(), -12345)
_case("A6 price parses to a float", f.price(), 10.25)
_case("A7 no error recorded", f.error, "")

f = FormFields({"quantity": "12345.5"})
_case("A8 fractional share count rejected", f.quantity(), None)
_case("A9 error names the field and the value", f.error,
      "Quantity must be a whole number, not '12345.5'.")

f = FormFields({"quantity": "", "price": "1"})
_case("A10 blank quantity rejected", f.quantity(), None)
_case("A11 blank charge defaults to zero", FormFields({}).charge("brokerage"), 0.0)

# The rejected form must re-render with what was typed, so it is not lost.
f = FormFields({"quantity": "oops", "price": "10.25", "trade_date": "2026-01-02"})
f.quantity(); f.price(); f.text("trade_date")
_case("A12 rejected value echoed back", f.values["quantity"], "oops")
_case("A13 parsed sibling kept as parsed", f.values["price"], 10.25)

# Only the first problem is reported, so the flash message stays readable.
f = FormFields({"quantity": "oops", "price": "nope"})
f.quantity(); f.price()
_case("A14 first problem reported", f.error, "Quantity must be a whole number, not 'oops'.")


# --- Case B: the routes ------------------------------------------------------
print("B  routes")
with sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True) as live:
    live.row_factory = sqlite3.Row
    sample = live.execute(
        "SELECT t.ref_num, t.trade_date, t.value_date, t.bank_ref, t.code_ref, "
        "       t.transaction_type, t.counter_bank_ref "
        "FROM tbl_transaction t WHERE t.transaction_type = 'Transfer-Out' "
        "AND t.counter_bank_ref IS NOT NULL ORDER BY t.ref_num DESC LIMIT 1"
    ).fetchone()
    other_bank = live.execute(
        "SELECT ref_num FROM tbl_bank_account WHERE ref_num != ? LIMIT 1",
        (sample["bank_ref"],)
    ).fetchone()

tmpdir = tempfile.mkdtemp(prefix="ltv_verify_qty_")
try:
    scratch_db = os.path.join(tmpdir, "LTV Stocks.db")
    shutil.copy2(LIVE_DB, scratch_db)

    app = create_app(test_config={"LOGIN_DISABLED": True, "WTF_CSRF_ENABLED": False})
    app.config["DATABASE"] = scratch_db
    client = app.test_client()

    common = {
        "trade_date": sample["trade_date"],
        "value_date": sample["value_date"],
        "bank_ref": str(sample["bank_ref"]),
        "code_ref": str(sample["code_ref"]),
    }

    # B1: the reported 500 -- a Transfer-Out of -12,345 shares.
    r = client.post("/trades/stock_transfer", data=dict(
        common, transaction_type="Transfer-Out", quantity="-12,345",
        price="10.25", counter_bank_ref=str(other_bank["ref_num"])),
        follow_redirects=False)
    _case("B1 /trades/stock_transfer status", r.status_code < 500, True)

    # B2: a plain Buy with a separator, through the long-book form.
    r = client.post("/trades/add", data=dict(
        common, transaction_type="Buy (Spot)", quantity="1,500", price="12.34"),
        follow_redirects=False)
    _case("B2 /trades/add status", r.status_code < 500, True)

    # B3: genuinely bad input is refused, not stored and not a 500. The form
    # comes back (200) rather than redirecting to a saved record.
    r = client.post("/trades/add", data=dict(
        common, transaction_type="Buy (Spot)", quantity="12x4", price="12.34"),
        follow_redirects=False)
    _case("B3 /trades/add rejects a non-number", r.status_code, 200)

    # B4: review.edit passed the raw string into SQL. Whatever it stores must be
    # a number -- a TEXT quantity poisons every SUM() that touches the row.
    r = client.post(f"/review/{sample['ref_num']}/edit", data={
        "trade_date": sample["trade_date"], "value_date": sample["value_date"],
        "transaction_type": sample["transaction_type"],
        "quantity": "-12,345", "price": "10.25",
    }, follow_redirects=False)
    _case("B4 /review/<id>/edit status", r.status_code < 500, True)

    with sqlite3.connect(scratch_db) as after:
        stored = after.execute(
            "SELECT quantity, typeof(quantity) FROM tbl_transaction WHERE ref_num = ?",
            (sample["ref_num"],)
        ).fetchone()
    _case("B5 review.edit stored a number, not text", stored[1] in ("integer", "real"), True)
    _case("B6 review.edit stored the right number", stored[0], -12345)

    # B7: nothing anywhere in the scratch database is a non-numeric quantity.
    with sqlite3.connect(scratch_db) as after:
        bad = after.execute(
            "SELECT COUNT(*) FROM tbl_transaction "
            "WHERE typeof(quantity) NOT IN ('integer', 'real')"
        ).fetchone()[0]
    _case("B7 no text quantities in the table", bad, 0)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)


# --- Case C: structural ------------------------------------------------------
print("C  structural")
# A form value must not reach int()/float() directly, and must not be handed to
# SQL unparsed. Both shapes are what produced this bug; both are now spelled
# with FormFields, so their absence is the property to hold.
_RAW_COERCION = re.compile(r"\b(?:int|float)\s*\(\s*(?:abs\s*\(\s*)?request\.form")
_QTY_STRAIGHT_TO_SQL = re.compile(r"request\.form(?:\.get)?[\[(]\s*['\"](?:quantity|price)['\"]")

offenders = []
for root, dirs, files in os.walk(os.path.join(SERVER, "ltv_app")):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for name in files:
        if not name.endswith(".py"):
            continue
        path = os.path.join(root, name)
        rel = os.path.relpath(path, SERVER).replace("\\", "/")
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if _RAW_COERCION.search(line):
                    offenders.append(f"{rel}:{lineno} raw coercion: {line.strip()[:70]}")
                elif _QTY_STRAIGHT_TO_SQL.search(line):
                    offenders.append(f"{rel}:{lineno} unparsed: {line.strip()[:70]}")

for o in offenders:
    print(f"      {o}")
_case("C form values coerced without FormFields", len(offenders), 0)

print("RESULT:", "ALL PASS" if _ok else "FAIL")
sys.exit(0 if _ok else 1)
