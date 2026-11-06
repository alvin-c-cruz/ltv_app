"""Regression harness: the Blocked Unblocked edition's figures as of a date (plan A).

Spec: docs/superpowers/specs/2026-11-02-blocked-unblocked-design.md (approved 6 Nov 2026), sections 3 and 8.
The app's figures (ltv_app/blueprints/blocked_unblocked/edition.py) are tied to a second read of the ledger tables
written here (the 30 Oct work order's calc.py method), and, when given, to Alvin's 30 Oct edition and the ledger
backup it was built from. On temp copies only:

  I1 positions and shares to block equal the second path, pair by pair (dev copy at its last trade date; with the
     evidence, also the 30 Oct ledger);
  I2 blocked, unblocked and short follow the rulings: a long row blocks min(to block, shares), never below 0
     (D7c); a short row blocks nothing and carries its shares as Short (F6);
  I3 shares to block as of D: a period ending on or before D counts as received, flagged or not, and one ending
     after D does not, flagged or not (ruling 6);
  I4 a pair sold out on D with a live contract keeps its row and reads 0 (rulings of 4 and 6 Nov);
  E1 (with --reference and --ledger) 30 Oct: the positions with shares, their shares and averages equal the
     edition's Equities sheet;
  E2 (same) the second path with the old flag rule reproduces the edition's shares to block on every long row; the
     number of pairs the date rule changes is printed, as a count.
No figure is printed.

Run: ..\\venv\\Scripts\\python.exe scripts\\verify_blocked_unblocked_edition.py
       [--reference "<30 Oct edition .xlsm>" --ledger "<LTV Stocks 2026-10-30-1355.db>"]
"""
import argparse
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import warnings
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.blocked_unblocked.edition import LONG, SHORT, build_edition

SHORT_TYPES = ("Sell (Short)", "Buy (Pay Short)")
CHARGES = ("brokerage", "commission", "foreign_charge", "stamp_duty", "misc")
EVIDENCE_DATE = "2026-10-30"
ok = True


def case(label, passed):
    global ok
    ok = ok and bool(passed)
    print(f"  {label}: {'PASS' if passed else 'FAIL'}")


def copy_db(source):
    """A temp copy made through SQLite's backup API, the source opened read-only."""
    path = os.path.join(tempfile.mkdtemp(), "copy.db")
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(path)
    src.backup(dst)
    dst.close()
    src.close()
    return path


def boot(path):
    return create_app({"DATABASE": path, "LOGIN_DISABLED": True, "WTF_CSRF_ENABLED": False})


def norm(code):
    code = str(code).strip().upper()
    return (code.lstrip("0") or "0") if code.isdigit() else code


# ---- the second path: the ledger tables read directly ----

def replay_long(rows):
    bal, cost = 0, 0.0
    for r in rows:
        q, p = r["quantity"], r["price"]
        amt = q * p + sum(r[k] for k in CHARGES)
        if q > 0:
            if bal >= 0:
                cost += amt
            elif bal + q <= 0:
                cost = 0.0
            else:
                cost = (bal + q) / q * amt
        elif bal > 0:
            cost = cost - cost * -q / bal if bal + q > 0 else 0.0
        else:
            cost = 0.0
        bal += q
    return bal, cost


def replay_short(rows):
    bal, cost, average = 0, 0.0, None
    for r in rows:
        q, charges = r["quantity"], sum(r[k] or 0 for k in CHARGES)
        if q < 0 and bal <= 0:
            cost += -q * r["price"] - charges
        elif q > 0 and bal < 0:
            cost = cost * (1 - q / -bal) if -bal > q else 0.0
        bal += q
        if bal < 0:
            average = cost / -bal
    return bal, average


def second_to_block(db, as_of, rule="date"):
    """{(bank_ref, code_ref): shares to block}. rule "date": a period is still to come when it ends after as_of;
    rule "flag": when its received column is empty (the app's rule before 6 Nov)."""
    to_block = defaultdict(int)
    for c in db.execute("SELECT * FROM tbl_stock_contract WHERE status='active' AND transaction_type='DECU' "
                        "AND trade_date<=?", (as_of,)).fetchall():
        days = 0
        for per in db.execute("SELECT days, end_date, received FROM tbl_stock_contract_period WHERE contract_ref=?",
                              (c["ref_num"],)):
            d = int(float(str(per["days"] or 0).replace(",", "") or 0))
            still_due = per["end_date"] > as_of if rule == "date" else not per["received"]
            days += d if still_due else 0
        to_block[(c["bank_ref"], c["code_ref"])] += c["daily_shares"] * days * (2 if c["leveraged"] == "Yes" else 1)
    return dict(to_block)


def second_live(db, as_of):
    return {(r[0], r[1]) for r in db.execute(
        "SELECT DISTINCT c.bank_ref, c.code_ref FROM tbl_stock_contract c "
        "JOIN tbl_stock_contract_period p ON p.contract_ref = c.ref_num "
        "WHERE c.status='active' AND c.trade_date<=? AND p.end_date>?", (as_of, as_of))}


def second_positions(db, as_of):
    """{(bank_ref, code_ref, side): (shares, average)} for every row the edition must carry."""
    positions = {}
    pairs = db.execute(
        "SELECT DISTINCT t.bank_ref, t.code_ref, b.transaction_basis AS tb FROM tbl_transaction t "
        "JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "WHERE t.trade_date<=? AND t.transaction_type NOT IN (?, ?)", (as_of,) + SHORT_TYPES).fetchall()
    for p in pairs:
        rows = db.execute(
            "SELECT tbl_transaction.* FROM tbl_transaction JOIN tbl_transaction_type USING (transaction_type) "
            "WHERE tbl_transaction.bank_ref=? AND tbl_transaction.code_ref=? AND tbl_transaction.trade_date<=? "
            "AND tbl_transaction.transaction_type NOT IN (?, ?) "
            f"ORDER BY tbl_transaction.{p['tb']}, tbl_transaction_type.priority, tbl_transaction.ref_num",
            (p["bank_ref"], p["code_ref"], as_of) + SHORT_TYPES).fetchall()
        bal, cost = replay_long(rows)
        positions[(p["bank_ref"], p["code_ref"], LONG)] = (bal, cost / bal if bal else 0.0)
    for p in db.execute("SELECT DISTINCT bank_ref, code_ref FROM tbl_transaction_short WHERE trade_date<=?",
                        (as_of,)).fetchall():
        rows = db.execute("SELECT * FROM tbl_transaction_short WHERE bank_ref=? AND code_ref=? AND trade_date<=? "
                          "ORDER BY trade_date, ref_num", (p["bank_ref"], p["code_ref"], as_of)).fetchall()
        bal, average = replay_short(rows)
        if bal < 0:
            positions[(p["bank_ref"], p["code_ref"], SHORT)] = (bal, round(average, 4) if average is not None else 0.0)
    live = second_live(db, as_of)
    expected = {k: v for k, v in positions.items() if v[0]}
    for pair in live:
        expected.setdefault(pair + (LONG,), positions.get(pair + (LONG,), (0, 0.0)))
    return expected


def edition_map(edition):
    return {(r.bank_ref, r.code_ref, r.side): r for r in edition.rows}


# ---- cases ----

def case_i1(db, as_of, label):
    expected = second_positions(db, as_of)
    to_block = second_to_block(db, as_of)
    rows = edition_map(build_edition(db, as_of))
    same_keys = bool(rows) and set(rows) == set(expected)
    figures = all(rows[k].shares == v[0] and abs(rows[k].average - v[1]) < 1e-6
                  for k, v in expected.items() if k in rows)
    blocks = all(r.to_block == (to_block.get(k[:2], 0) if k[2] == LONG else 0) for k, r in rows.items())
    case(f"I1 {label}: positions and shares to block equal the second path", same_keys and figures and blocks)


def case_i2(db, as_of):
    rows = build_edition(db, as_of).rows

    def right(r):
        if r.side == SHORT:
            return r.blocked == 0 and r.unblocked == 0 and r.short == r.shares
        want = max(0, min(r.to_block, r.shares))
        return r.blocked == want and r.unblocked == r.shares - want and r.short == 0

    both_kinds = any(r.side == SHORT for r in rows) and any(r.side == LONG and r.to_block for r in rows)
    case("I2 blocked, unblocked and short follow D7c and F6",
         both_kinds and all(right(r) for r in rows)
         and all(r.blocked + r.unblocked + r.short == r.shares for r in rows))


def case_i3(source):
    app = boot(copy_db(source))
    with app.app_context():
        db = get_db()
        found = None
        contracts = db.execute("SELECT ref_num, bank_ref, code_ref FROM tbl_stock_contract "
                               "WHERE status='active' AND transaction_type='DECU' ORDER BY ref_num").fetchall()
        for c in contracts:
            ends = [r[0] for r in db.execute("SELECT end_date FROM tbl_stock_contract_period WHERE contract_ref=? "
                                             "ORDER BY end_date", (c["ref_num"],))]
            if len(ends) < 3:
                continue
            as_of = ends[0]
            # The opposite of the date rule: every period ending on or before as_of left unflagged,
            # every later one flagged received.
            db.execute("UPDATE tbl_stock_contract_period SET received=NULL WHERE contract_ref=? AND end_date<=?",
                       (c["ref_num"], as_of))
            db.execute("UPDATE tbl_stock_contract_period SET received=1 WHERE contract_ref=? AND end_date>?",
                       (c["ref_num"], as_of))
            db.commit()
            pair = (c["bank_ref"], c["code_ref"])
            by_date = second_to_block(db, as_of, "date").get(pair, 0)
            if by_date != second_to_block(db, as_of, "flag").get(pair, 0):
                found = (pair, as_of, by_date)
                break
        row = edition_map(build_edition(db, found[1])).get(found[0] + (LONG,)) if found else None
    case("I3 shares to block count the periods ending after D, whatever their flags",
         found and row and row.to_block == found[2])


def case_i4(source, as_of):
    app = boot(copy_db(source))
    with app.app_context():
        db = get_db()
        rows = edition_map(build_edition(db, as_of))
        live = second_live(db, as_of)
        pick = next((k for k, r in rows.items() if k[2] == LONG and r.shares > 0 and k[:2] in live), None)
        row = None
        if pick:
            db.execute("INSERT INTO tbl_transaction (trade_date, value_date, bank_ref, code_ref, transaction_type, "
                       "quantity, price, brokerage, commission, foreign_charge, stamp_duty, misc, reviewed, locked, "
                       "no_charges) VALUES (?, ?, ?, ?, 'Sell (Spot)', ?, 1, 0, 0, 0, 0, 0, 0, 0, 0)",
                       (as_of, as_of, pick[0], pick[1], -rows[pick].shares))
            db.commit()
            row = edition_map(build_edition(db, as_of)).get(pick)
    zero = row is not None and row.shares == 0 and row.average == 0 and row.cost == 0 \
        and row.blocked == 0 and row.unblocked == 0
    priced = row is not None and (row.close is None or (row.market == 0 and row.gain == 0 and row.gain_pct == 0))
    case("I4 a pair sold out with a live contract keeps its row and reads 0", pick and zero and priced)


def reference_rows(path):
    """{(bank_id, code, side): [shares, shares x average, to block]} from the edition's Equities sheet."""
    tmp = os.path.join(tempfile.mkdtemp(), "reference.xlsm")
    shutil.copy(path, tmp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ws = load_workbook(tmp, data_only=True, read_only=True)["Equities"]
        out = defaultdict(lambda: [0, 0.0, 0])
        for row in ws.iter_rows(min_row=4, values_only=True):
            key, qty, avg, to_block, account = row[1], row[2], row[3], row[9], row[10]
            if not (account and isinstance(key, str) and isinstance(qty, (int, float))):
                continue
            side = SHORT if key.startswith("(") else LONG
            entry = out[(account, norm(key.split(") ")[-1].split(":")[0]), side)]
            entry[0] += qty
            entry[1] += qty * (avg or 0)
            entry[2] = to_block if isinstance(to_block, (int, float)) else 0
    return out


def case_e1_e2(reference, ledger):
    ref = reference_rows(reference)
    app = boot(copy_db(ledger))
    with app.app_context():
        db = get_db()
        case_i1(db, EVIDENCE_DATE, "30 Oct ledger")
        held = {(r.bank_id, norm(r.code), r.side): r for r in build_edition(db, EVIDENCE_DATE).rows if r.shares}
        ref_held = {k: v for k, v in ref.items() if v[0]}
        figures = all(held[k].shares == v[0] and abs(held[k].average - v[1] / v[0]) < 1e-6
                      for k, v in ref_held.items() if k in held)
        case("E1 30 Oct: the positions, their shares and averages equal Alvin's edition",
             ref_held and set(held) == set(ref_held) and figures)
        flag = second_to_block(db, EVIDENCE_DATE, "flag")
        date = second_to_block(db, EVIDENCE_DATE, "date")
        bank_of = {r["bank_id"]: r["ref_num"] for r in db.execute("SELECT ref_num, bank_id FROM tbl_bank_account")}
        code_of = {norm(r["code"]): r["ref_num"] for r in db.execute("SELECT ref_num, code FROM tbl_code")}
        longs = {k: v for k, v in ref.items() if k[2] == LONG}
        reproduces = all(flag.get((bank_of.get(k[0]), code_of.get(k[1])), 0) == v[2] for k, v in longs.items())
        case("E2 30 Oct: the old flag rule reproduces the edition's shares to block", longs and reproduces)
        changed = sum(1 for p in set(flag) | set(date) if flag.get(p, 0) != date.get(p, 0))
        print(f"  pairs whose shares to block the date rule changes on 30 Oct: {changed}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", help="Alvin's 30 Oct edition (.xlsm); read from a temp copy")
    parser.add_argument("--ledger", help="the ledger backup the 30 Oct edition was built from")
    args = parser.parse_args()

    dev = os.path.join(SERVER, "instance", "LTV Stocks.db")
    app = boot(copy_db(dev))
    with app.app_context():
        db = get_db()
        as_of = db.execute("SELECT max(trade_date) FROM tbl_transaction").fetchone()[0]
        case_i1(db, as_of, "dev copy")
        case_i2(db, as_of)
    case_i3(dev)
    case_i4(dev, as_of)
    if args.reference and args.ledger:
        case_e1_e2(args.reference, args.ledger)
    else:
        print("  E1, E2: not run (give --reference and --ledger)")

    print("RESULT:", "ALL PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
