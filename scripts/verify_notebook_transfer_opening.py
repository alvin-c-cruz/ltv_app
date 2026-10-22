"""Regression harness: a transfer in the notebook must open at the balance left
after the day's other activity in that account and stock, not at the day open.

The notebook prints the day's trades first, each (account, stock) ending on its
remaining-shares line, and the "Transfer of Stocks" section after them. The
transfer section seeded each account's balance with `_opening_balance` --
trade_date < the notebook date -- so when the same account also sold, fixed or
bought that stock on the day, the transfer opened at the day-open figure while
the trades section above it had already moved on. Found 2026-10-21 on the
2026-10-20 notebook: two of its three transfers opened above the remaining
shares printed for the same account a few rows earlier.

Expected openings are derived from the database at runtime: the balance before
the date, plus every same-day non-transfer row of that account and stock (the
rows the trades section prints), carried through earlier same-day transfers of
that stock in the order the notebook lists them. Fixtures are found, not named,
and failures never print a balance -- the repository is public.

Each notebook is generated into instance/temp/ exactly as the /notebook/ route
does; a file this script created is removed after it is read. The database is
only read.

Run:   .venv/Scripts/python.exe scripts/verify_notebook_transfer_opening.py [db_path] [--all]
       (default: instance/LTV Stocks.db, the 25 most recent affected dates)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.notebook.extensions import CreateNotebook, get_transactions, get_transfers

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")
RECENT = 25

_TRANSFER_TYPES = ("Transfer-In", "Transfer-Out")


def _open(db_path):
    app = create_app()
    app.config["DATABASE"] = db_path
    ctx = app.app_context()
    ctx.push()
    return ctx, get_db()


def _affected_dates(db):
    # Dates on which a transfer leg's account also has a non-transfer row in the
    # same stock: the shape where day-open and post-trade balances differ.
    rows = db.execute(
        "SELECT DISTINCT x.trade_date FROM tbl_transaction x "
        "WHERE x.transaction_type IN (?, ?) "
        "  AND EXISTS (SELECT 1 FROM tbl_transaction t "
        "              WHERE t.trade_date = x.trade_date AND t.bank_ref = x.bank_ref "
        "                AND t.code_ref = x.code_ref "
        "                AND t.transaction_type NOT IN (?, ?)) "
        "ORDER BY x.trade_date",
        _TRANSFER_TYPES + _TRANSFER_TYPES,
    ).fetchall()
    return [r[0] for r in rows]


def _balance(db, bank_name, code, trade_date, same_day):
    sql = (
        "SELECT SUM(t.quantity) FROM tbl_transaction t "
        "INNER JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "INNER JOIN tbl_code c ON c.ref_num = t.code_ref "
        "WHERE b.bank_name = ? AND c.code = ? AND "
    )
    if same_day:
        sql += "t.trade_date = ? AND t.transaction_type NOT IN (?, ?)"
        args = (bank_name, code, trade_date) + _TRANSFER_TYPES
    else:
        sql += "t.trade_date < ?"
        args = (bank_name, code, trade_date)
    value = db.execute(sql, args).fetchone()[0]
    return int(value) if value is not None else 0


def _expected(db, trade_date, transfers):
    running, day_open, out = {}, {}, []
    for pair in transfers:
        code, qty = pair["code"], int(pair["quantity"])
        for bank in (pair["out_bank"], pair["in_bank"]):
            if (bank, code) not in running:
                day_open[(bank, code)] = _balance(db, bank, code, trade_date, False)
                running[(bank, code)] = (day_open[(bank, code)]
                                         + _balance(db, bank, code, trade_date, True))
        out.append({
            "code": code,
            "out": (pair["out_bank_id"], running[(pair["out_bank"], code)],
                    day_open[(pair["out_bank"], code)]),
            "in": (pair["in_bank_id"], running[(pair["in_bank"], code)],
                   day_open[(pair["in_bank"], code)]),
        })
        running[(pair["out_bank"], code)] -= qty
        running[(pair["in_bank"], code)] += qty
    return out


def _printed_openings(path):
    # Each pair block: title "Transfer <stock> (<code>)", from, to, qty, bank
    # headers, then the opening row (E = from account, M = to account).
    ws = load_workbook(path)["notebook"]
    start = next(r for r in range(1, ws.max_row + 1)
                 if ws[f"C{r}"].value == "Transfer of Stocks")
    found = []
    for r in range(start + 1, ws.max_row + 1):
        title = ws[f"C{r}"].value
        if isinstance(title, str) and title.startswith("Transfer "):
            code = re.search(r"\(([^()]*)\)\s*$", title).group(1)
            found.append((code, ws[f"E{r + 5}"].value, ws[f"M{r + 5}"].value))
    return found


def _check_date(db, trade_date):
    transfers = get_transfers(db=db, trade_date=trade_date)
    if not transfers:
        return True, 0
    expected = _expected(db, trade_date, transfers)

    path = None
    existed = False
    try:
        transactions = get_transactions(db=db, trade_date=trade_date)
        path = CreateNotebook(db=db, trade_date=trade_date,
                              transactions=transactions, transfers=transfers).filename
        printed = _printed_openings(path)
    finally:
        if path and os.path.exists(path):
            os.remove(path)

    ok = len(printed) == len(expected)
    if not ok:
        print(f"  {trade_date}: FAIL  {len(expected)} transfer(s) expected, {len(printed)} printed")
        return False, len(expected)

    for exp, (code, got_out, got_in) in zip(expected, printed):
        for side, got in (("out", got_out), ("in", got_in)):
            bank_id, want, day_open = exp[side]
            if code != exp["code"] or got != want:
                hint = " (prints the day-open balance)" if got == day_open else ""
                print(f"  {trade_date} {exp['code']} {side} {bank_id}: FAIL{hint}")
                ok = False
    return ok, len(expected)


def main():
    args = [a for a in sys.argv[1:] if a != "--all"]
    db_path = args[0] if args else DB_PATH
    ctx, db = _open(db_path)
    try:
        dates = _affected_dates(db)
        if not dates:
            print("  FAIL: no date with a transfer and a same-day trade in the same account and stock")
            sys.exit(1)
        if "--all" not in sys.argv:
            dates = dates[-RECENT:]

        ok, pairs = True, 0
        for d in dates:
            date_ok, n = _check_date(db, d)
            ok &= date_ok
            pairs += n
        print(f"  {len(dates)} affected date(s), {pairs} transfer pair(s) checked")
    finally:
        ctx.pop()

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
