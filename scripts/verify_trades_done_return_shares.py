"""Regression harness: Trades Done with gain loss heads a return RETURN SHARES and shows its gain as a cover does.

A Return Shares row gives borrowed shares back out of the long book and closes as many of the short
(transactions.borrow_return_shares books both halves). Its block was headed a second "SELL" and showed
no gain. Alvin, 6 Nov 2026: the block reads "RETURN SHARES", merged across A:C, and "the return shares
should have profit as in pay short": the shares at the short average carried just before the return,
less their value at the return's price.

On a copy of the database:
  H1 every day with a Return Shares row: its block reads RETURN SHARES, merged A:C, 14 pt bold, centred;
  H2 each return row: L = G*O, M = L-H, N = M/L, O = the short average just before its short-book half
     (replayed here from tbl_transaction_short), under the headers "Short Sale <ccy>" and the gain/loss
     formulas;
  H3 a return booked through + Borrow/Return on a new day, followed by a short sale the same day: O is
     the average before the return, not the day's closing average;
  H4 each return is printed once, from the long book: the short-book pass does not repeat it;
  U1 every other day with long- or short-book trades, of the last LOOKBACK such days, gives the same
     workbook as the generator at BASE (before this change), cell for cell, merges included; E2 (the
     time made) aside;
  B1 a Borrow Shares day booked through + Borrow/Return: headed BORROW SHARES (Alvin, 6 Nov: "yes"),
     merged A:C, 14 pt bold, centred;
  U2 that day is otherwise the same workbook as at BASE, where it was headed BUY.
Re-pin BASE when the generator changes on purpose. No client figure is printed.

Run: ../venv/Scripts/python.exe scripts/verify_trades_done_return_shares.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from flask import url_for
from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.transactions.extensions import TransactionSummary
from ltv_app.blueprints.transactions.extensions import download_trades_done_with_gain_loss as excel

BASE = "7ad857c"  # the generator before Return Shares got its own header and gain
MODULE = "ltv_app/blueprints/transactions/extensions/download_trades_done_with_gain_loss.py"
LOOKBACK = 25
RETURN = "Return Shares"
CHARGES = ("brokerage", "commission", "foreign_charge", "stamp_duty", "misc")

_dir = tempfile.mkdtemp()
_db = os.path.join(_dir, "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, passed):
    global ok
    ok = ok and passed
    print(f"  {label}: {'PASS' if passed else 'FAIL'}")


def _base_module():
    source = subprocess.run(["git", "-C", SERVER, "show", f"{BASE}:{MODULE}"],
                            capture_output=True, check=True).stdout
    path = os.path.join(_dir, "trades_done_at_base.py")
    with open(path, "wb") as f:
        f.write(source)
    # Named inside the package, so its relative imports resolve.
    spec = importlib.util.spec_from_file_location(
        "ltv_app.blueprints.transactions.extensions._trades_done_at_base", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet(module, db, day):
    module.fetch_hkd_rate = lambda ccy: (1.0, "test")
    out = module.DownloadTradesDoneWithGainLoss(db=db, trade_date=day,
                                                trade_summary=TransactionSummary(db, day)).output
    return load_workbook(out).active


def _dump(ws):
    cells = {}
    for row in ws.iter_rows():
        for c in row:
            if c.coordinate == "E2":
                continue
            look = (c.value, c.number_format, c.font.b, c.font.sz, c.alignment.horizontal,
                    c.fill.fgColor.rgb if c.fill and c.fill.fill_type else None,
                    bool(c.border.top.style))
            if look != (None, "General", False, 11, None, None, False):
                cells[c.coordinate] = look
    heights = {r: d.height for r, d in ws.row_dimensions.items() if d.height}
    return cells, sorted(str(m) for m in ws.merged_cells.ranges), heights, ws.print_area


def _replay(rows):
    """Short average after the rows, a cover taking off its share of the cost (None if never short)."""
    balance, cost, average = 0, 0.0, None
    for r in rows:
        qty, charges = r["quantity"], sum(r[k] or 0 for k in CHARGES)
        if qty < 0 and balance <= 0:
            cost += -qty * r["price"] - charges
        elif qty > 0 and balance < 0:
            cost = cost * (1 - qty / -balance) if -balance > qty else 0.0
        balance += qty
        if balance < 0:
            average = cost / -balance
    return average


def _short_rows(db, bank_ref, code_ref, day, before_ref=None):
    sql = ("SELECT * FROM tbl_transaction_short WHERE bank_ref=? AND code_ref=? AND "
           + ("trade_date<=?" if before_ref is None else "(trade_date<? OR (trade_date=? AND ref_num<?))")
           + " ORDER BY trade_date, ref_num")
    args = (day,) if before_ref is None else (day, day, before_ref)
    return db.execute(sql, (bank_ref, code_ref) + args).fetchall()


def _expected_returns(db, day):
    """{(bank_name, stock, shares, price): [short average before each return's short half]}.
    The k-th long half of a day, account, stock and size pairs with the k-th short half."""
    def rows(table, sign):
        return db.execute(
            f"SELECT t.ref_num, t.bank_ref, t.code_ref, {sign}t.quantity AS qty, t.price, "
            "       b.bank_name, c.stock_name, c.code "
            f"FROM {table} t JOIN tbl_bank_account b ON b.ref_num=t.bank_ref "
            "JOIN tbl_code c ON c.ref_num=t.code_ref "
            "WHERE t.trade_date=? AND t.transaction_type=? ORDER BY t.ref_num", (day, RETURN)).fetchall()
    shorts = defaultdict(list)
    for s in rows("tbl_transaction_short", ""):
        shorts[(s["bank_ref"], s["code_ref"], s["qty"])].append(s["ref_num"])
    expected, taken = defaultdict(list), defaultdict(int)
    for r in rows("tbl_transaction", "-"):
        key = (r["bank_ref"], r["code_ref"], r["qty"])
        pair = shorts[key][taken[key]] if taken[key] < len(shorts[key]) else None
        taken[key] += 1
        average = _replay(_short_rows(db, r["bank_ref"], r["code_ref"], day, pair)) if pair else None
        expected[(r["bank_name"], f"{r['stock_name']} ({r['code']})", r["qty"],
                  round(r["price"], 4))].append(average)
    return expected


def _check_return_day(db, day):
    """(H1 header ok, H2 rows ok, H4 printed once) for one day."""
    ws = _sheet(excel, db, day)
    merged = {str(m) for m in ws.merged_cells.ranges}
    expected = _expected_returns(db, day)
    got, header_ok, rows_ok = defaultdict(list), True, True
    for r in range(1, ws.max_row + 1):
        if ws[f"D{r}"].value != RETURN:
            continue
        head = max(h for h in range(1, r) if ws[f"A{h}"].value in ("BUY", "SELL", "RETURN SHARES"))
        a = ws[f"A{head}"]
        header_ok &= (a.value == "RETURN SHARES" and f"A{head}:C{head}" in merged and a.font.b
                      and a.font.sz == 14 and a.alignment.horizontal == "center")
        rows_ok &= (ws[f"L{r}"].value == f"=G{r}*O{r}" and ws[f"M{r}"].value == f"=L{r}-H{r}"
                    and ws[f"N{r}"].value == f"=M{r}/L{r}"
                    and ws[f"L{head}"].value == f"Short Sale {ws[f'D{head}'].value}"
                    and str(ws[f"M{head}"].value).startswith("=IF(COUNTIF(M")
                    and str(ws[f"N{head}"].value).startswith('="% "&IF(COUNTIF(N'))
        got[(ws[f"A{r}"].value, ws[f"C{r}"].value, ws[f"G{r}"].value, ws[f"E{r}"].value)].append(ws[f"O{r}"].value)

    def norm(d):
        return {k: sorted(round(v, 6) if isinstance(v, (int, float)) else v for v in vals) for k, vals in d.items()}
    rows_ok &= bool(got) and norm(got) == norm(expected)
    once = sum(len(v) for v in got.values()) == sum(len(v) for v in expected.values())
    return header_ok and bool(got), rows_ok, once


def _book(path, **form):
    with app.test_request_context():
        url = url_for(path)
    client.post(url, data=form)


with app.app_context():
    db = get_db()
    real_feed = excel.fetch_hkd_rate
    base = _base_module()

    # H1, H2, H4 on the ledger's own returns
    return_days = [r[0][:10] for r in db.execute(
        "SELECT DISTINCT trade_date FROM tbl_transaction WHERE transaction_type=? ORDER BY 1", (RETURN,))]
    results = [_check_return_day(db, d) for d in return_days]
    print(f"  {len(return_days)} day(s) with a Return Shares row in the copy")

    # H3: a new day, the first open short in the copy: a return of a quarter of it, then a short sale
    last = max(db.execute("SELECT max(trade_date) FROM tbl_transaction").fetchone()[0][:10],
               db.execute("SELECT max(trade_date) FROM tbl_transaction_short").fetchone()[0][:10])
    day = datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)
    while day.isoweekday() > 5:
        day += timedelta(days=1)
    new_day = str(day.date())
    value_day = str((day + timedelta(days=2)).date())
    bank_ref, code_ref, balance = db.execute(
        "SELECT bank_ref, code_ref, sum(quantity) FROM tbl_transaction_short GROUP BY 1, 2 "
        "HAVING sum(quantity) < 0 ORDER BY 1, 2 LIMIT 1").fetchone()
    before = _replay(_short_rows(db, bank_ref, code_ref, new_day))
    returned = max(1, -balance // 4)
    _book("transactions.borrow_return_shares", trade_date=new_day, value_date=value_day, bank_ref=bank_ref,
          code_ref=code_ref, transaction_type=RETURN, quantity=returned, price=round(before * 0.6, 2))
    _book("transactions.add_short", trade_date=new_day, value_date=value_day, bank_ref=bank_ref,
          code_ref=code_ref, transaction_type="Sell (Short)", quantity=-returned, price=round(before * 0.5, 2))
    closing = _replay(_short_rows(db, bank_ref, code_ref, new_day))
    booked = db.execute("SELECT count(*) FROM tbl_transaction WHERE trade_date=? AND transaction_type=?",
                        (new_day, RETURN)).fetchone()[0] == 1
    h3 = _check_return_day(db, new_day)
    distinct = closing is not None and abs(closing - before) > 1e-6
    expected = _expected_returns(db, new_day)
    _case("H1 a Return Shares block reads RETURN SHARES, merged A:C, 14 pt bold, centred",
          bool(results) and all(r[0] for r in results) and h3[0])
    _case("H2 a return row carries the cover's gain columns at the short average before it",
          bool(results) and all(r[1] for r in results) and h3[1])
    _case("H3 a same-day short sale after the return does not move the return's basis",
          booked and distinct and h3[1]
          and all(abs(v - before) < 1e-6 for vals in expected.values() for v in vals if v is not None))
    _case("H4 each return is printed once", bool(results) and all(r[2] for r in results) and h3[2])

    # U1: days without a return are unchanged against BASE
    days = [r[0][:10] for r in db.execute(
        "SELECT d FROM (SELECT DISTINCT substr(trade_date, 1, 10) AS d FROM tbl_transaction "
        "               WHERE transaction_type LIKE '%Spot%' OR transaction_type LIKE '%Short%' "
        "                  OR transaction_type LIKE 'Transfer%' OR transaction_type LIKE 'Borrow%' "
        "               UNION SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction_short) "
        "ORDER BY d DESC LIMIT ?", (LOOKBACK + len(return_days) + 1,))]
    days = [d for d in days if d not in return_days and d != new_day][:LOOKBACK]
    changed = [d for d in days if _dump(_sheet(excel, db, d)) != _dump(_sheet(base, db, d))]
    print(f"  {len(days)} day(s) without a return compared with {BASE}; {len(changed)} differ")
    _case("U1 a day without a return gives the same workbook as before", bool(days) and not changed)

    # B1, U2: a Borrow Shares day is headed BORROW SHARES and otherwise unchanged
    day += timedelta(days=1)
    while day.isoweekday() > 5:
        day += timedelta(days=1)
    borrow_day = str(day.date())
    _book("transactions.borrow_return_shares", trade_date=borrow_day, value_date=value_day, bank_ref=bank_ref,
          code_ref=code_ref, transaction_type="Borrow Shares", quantity=returned, price=round(before * 0.6, 2))
    ws = _sheet(excel, db, borrow_day)
    heads = [r for r in range(1, ws.max_row + 1)
             if ws[f"A{r}"].value in ("BUY", "SELL", "RETURN SHARES", "BORROW SHARES")]
    head = heads[0] if len(heads) == 1 else None
    a = ws[f"A{head}"] if head else None
    _case("B1 a Borrow Shares block reads BORROW SHARES, merged A:C, 14 pt bold, centred",
          head is not None and a.value == "BORROW SHARES"
          and f"A{head}:C{head}" in {str(m) for m in ws.merged_cells.ranges}
          and a.font.b and a.font.sz == 14 and a.alignment.horizontal == "center")
    cells, merges, heights, area = _dump(ws)
    if head:
        cells[f"A{head}"] = ("BUY",) + cells[f"A{head}"][1:]
        merges = [m for m in merges if m != f"A{head}:C{head}"]
    _case("U2 the Borrow Shares day is otherwise the same workbook as before",
          head is not None and (cells, merges, heights, area) == _dump(_sheet(base, db, borrow_day)))

    excel.fetch_hkd_rate = real_feed

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
