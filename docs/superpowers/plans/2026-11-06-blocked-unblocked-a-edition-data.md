# Blocked Unblocked, plan A: the edition's figures, the Equities sheet and the page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alvin opens a new page, picks a date (and optionally supplies a price set), and downloads
`<date> Blocked Unblocked.xlsx`, whose `Equities` sheet carries every account's positions, shares to block, blocked,
unblocked, short, price and market value as of that date, computed from the ledger.

**Architecture:** A new blueprint `blocked_unblocked`. `edition.py` computes one `EditionRow` per account and position
(long holding or short) from the ledger tables, using the app's own engines (`accumulate_position`,
`accumulate_short_position`, `get_short_average`). `price_set.py` reads a supplied price set without storing it.
`extensions/edition_workbook.py` writes the rows to an `Equities` sheet; the view serves it. This is the data layer
the printed sheets of plans B–D are drawn from. The harness ties the figures to a second, independent read of the
ledger tables and, when given the evidence, to Alvin's 30 Oct edition.

**Tech Stack:** Flask 3.1, raw sqlite3 via `get_db()`, Flask-WTF 1.2.2 (`FlaskForm`, `flask_wtf.file.FileField`),
openpyxl. No ORM, no migrations, no schema change.

**Spec:** `docs/superpowers/specs/2026-11-02-blocked-unblocked-design.md` (approved 6 Nov 2026). This plan implements
section 3 (inputs) with the 6 Nov rulings 1 (output: one `.xlsx`, page on demand), 2 (D7c: holdings include the day's
fixings), 3 (the holdings decide the rows), 4 (prices: D's close, or a supplied set never stored), 5 (any time), 6
(to block as of D), 10 (F6: shorts are not blocked) and 12 (short average at 4 dp); section 7's data sheet; and
section 8's cases 1 and 2 (inputs, Equities). Case 5, each printed close against the edition's `Closing` sheet, goes
with plan C, which prints them; this plan pins the close rule itself (case I5).

## Global Constraints

- **The GitHub repository is public.** No client figure, account balance, share count or price from the ledger or the
  evidence goes into code, tests, comments or commit messages. Harnesses compute expected values at runtime and never
  print a figure, only case names, counts and PASS/FAIL. Test-only constants (a price like `123.45`) are fine.
- **Never run anything inside `prod\`, and never against the live ledger** `C:\envs\assistant\clients\ltv\legacy\instance\LTV Stocks.db`.
  Harnesses run on temp copies made with SQLite's backup API, the source opened `mode=ro`.
- Boot harness apps with `create_app({"DATABASE": <temp copy>, "LOGIN_DISABLED": True, "WTF_CSRF_ENABLED": False})`,
  never a bare `create_app()` (it writes to its database at boot).
- Run everything from `C:\envs\assistant\products\ltv-app\app` with `..\venv\Scripts\python.exe`.
- Evidence files are read from a temp copy and never written beside.
- Commits: `feat(blocked_unblocked): …`, each ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  No release (`Bump version`), no push and no deploy in this plan: each needs Alvin's own word.
- `app/BUGS.md` is git-ignored; update it, never stage it.
- The edition's dates are `YYYY-MM-DD` strings; every date column in these tables holds exactly that (checked
  6 Nov 2026), so plain string comparison is correct.

## File Structure

| File | Responsibility |
|---|---|
| Create `ltv_app/blueprints/blocked_unblocked/__init__.py` | Exposes `bp` so `blueprints/__init__.py` registers it |
| Create `ltv_app/blueprints/blocked_unblocked/edition.py` | The figures: `EditionRow`, `Edition`, `build_edition()` and its parts |
| Create `ltv_app/blueprints/blocked_unblocked/price_set.py` | `PriceSet`, `read_price_set()`: a Yahoo CSV and/or pasted prices |
| Create `ltv_app/blueprints/blocked_unblocked/extensions/__init__.py` | Exports `EditionWorkbook` |
| Create `ltv_app/blueprints/blocked_unblocked/extensions/edition_workbook.py` | Writes the `Equities` sheet |
| Create `ltv_app/blueprints/blocked_unblocked/forms.py` | `EditionForm` |
| Create `ltv_app/blueprints/blocked_unblocked/views.py` | `bp`, the page and the download |
| Create `ltv_app/blueprints/blocked_unblocked/pages/blocked_unblocked/home.html` | The form |
| Modify `ltv_app/blueprints/__init__.py` | Import the new blueprint |
| Modify `ltv_app/templates/navbar.html:57` | A Reports link |
| Create `scripts/verify_blocked_unblocked_edition.py` | The harness, grown task by task |

---

### Task 1: The edition's positions and shares to block

**Files:**
- Create: `ltv_app/blueprints/blocked_unblocked/edition.py`
- Create: `ltv_app/blueprints/blocked_unblocked/__init__.py` (empty for now; Task 3 fills it)
- Test: `scripts/verify_blocked_unblocked_edition.py`

**Interfaces:**
- Consumes: `transactions.models.accumulate_position(rows) -> (balance, cost_to_date, last_average)`;
  `transactions.models.accumulate_short_position(rows) -> (balance, cost_to_date)` (rows must expose the five charge
  columns as numbers); `transactions.models.get_short_average(db, bank_ref, code_ref, trade_date, before_ref=None) -> float | None`;
  `term_sheet.models._to_int(value) -> int`.
- Produces (later tasks and plans B–D rely on these names):
  - `LONG = "Long"`, `SHORT = "Short"`.
  - `EditionRow` dataclass: fields `bank_ref:int, bank_id:str, bank_name:str, code_ref:int, code:str, stock_name:str,
    ccy:str, side:str, shares:float, average:float, to_block:float=0, close:float|None=None, close_from:str=""`;
    properties `cost, blocked, unblocked, short, market, gain, gain_pct, key`.
  - `Edition` dataclass: `as_of:str, rows:list[EditionRow], price_label:str, unpriced:list[str]`.
  - `build_edition(db, as_of:str, prices:dict[int,float]|None=None, price_label:str="") -> Edition`.
  - `long_positions(db, as_of) -> {(bank_ref, code_ref): (shares, average)}`,
    `short_positions(db, as_of) -> {(bank_ref, code_ref): (shares, average)}` (shares < 0 only),
    `shares_to_block(db, as_of) -> {(bank_ref, code_ref): shares}`, `live_contract_pairs(db, as_of) -> set`,
    `closes(db, code_refs, as_of) -> {code_ref: (price, date)}`.

- [ ] **Step 1: Write the failing harness**

Create `scripts/verify_blocked_unblocked_edition.py`:

```python
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
```

Also create the package so the import path exists, `ltv_app/blueprints/blocked_unblocked/__init__.py`, with this
single line (Task 3 replaces it):

```python
# The Blocked Unblocked edition; the blueprint is added in Task 3.
```

- [ ] **Step 2: Run it and watch it fail**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: `ImportError: cannot import name 'LONG' from 'ltv_app.blueprints.blocked_unblocked.edition'` (or
`ModuleNotFoundError` for `edition`).

- [ ] **Step 3: Write `edition.py`**

```python
"""The Blocked Unblocked edition's figures as of one date, from the ledger.

One row per account and position: an account's long holding of a stock, or its short. Every printed page of the
edition is drawn from these rows (spec docs/superpowers/specs/2026-11-02-blocked-unblocked-design.md, sections 3
and 7, approved 6 Nov 2026):

- holdings count every row traded on or before the date, in every account, so the day's fixings are in (D7c);
- shorts come from the Short Book, the average rounded to 4 dp as the Short Book page shows it (ruling 12);
- shares to block are the days of the live decumulators' periods ending after the date, flagged or not (ruling 6);
- a long row blocks min(to block, shares); a short row blocks nothing and is carried as Short (F6);
- a position nobody holds, with a live contract still running, keeps its row and reads 0 (rulings of 4 and 6 Nov);
- prices are the date's close, else the latest before it, unless a price set is supplied for the build (ruling 4).

Contract status is today's, not the date's: a contract knocked out since the date is no longer counted.
"""
from dataclasses import dataclass, field

from ..term_sheet.models import _to_int
from ..transactions.models import accumulate_position, accumulate_short_position, get_short_average

LONG, SHORT = "Long", "Short"
SHORT_TYPES = ("Sell (Short)", "Buy (Pay Short)")
CHARGES = ("brokerage", "commission", "foreign_charge", "stamp_duty", "misc")
BASIS_COLUMNS = ("trade_date", "value_date")


@dataclass
class EditionRow:
    bank_ref: int
    bank_id: str
    bank_name: str
    code_ref: int
    code: str
    stock_name: str
    ccy: str
    side: str
    shares: float
    average: float
    to_block: float = 0
    close: float | None = None
    close_from: str = ""

    @property
    def cost(self):
        return self.shares * self.average

    @property
    def blocked(self):
        return 0 if self.side == SHORT else max(0, min(self.to_block, self.shares))

    @property
    def unblocked(self):
        return 0 if self.side == SHORT else self.shares - self.blocked

    @property
    def short(self):
        return self.shares if self.side == SHORT else 0

    @property
    def market(self):
        return None if self.close is None else self.shares * self.close

    @property
    def gain(self):
        return None if self.close is None else self.market - self.cost

    @property
    def gain_pct(self):
        if self.close is None:
            return None
        return self.gain / abs(self.cost) if self.cost else 0.0

    @property
    def key(self):
        """The workbook's own key for the position: '175:HK', or '(S) 175:HK' for a short."""
        code = (self.code.lstrip("0") or "0") if self.code.isdigit() else self.code
        suffix = "HK" if self.ccy == "HKD" else self.ccy
        return f"{'(S) ' if self.side == SHORT else ''}{code}:{suffix}"


@dataclass
class Edition:
    as_of: str
    rows: list
    price_label: str
    unpriced: list = field(default_factory=list)


def long_positions(db, as_of):
    """{(bank_ref, code_ref): (shares, average)} for every account and stock with a long-book row traded on or
    before as_of. Replayed in the account's own basis order, then the type's priority, as the portfolio report
    replays them; the edition selects on trade date so the day's fixings count."""
    pairs = db.execute(
        "SELECT DISTINCT t.bank_ref, t.code_ref, b.transaction_basis FROM tbl_transaction t "
        "JOIN tbl_bank_account b ON b.ref_num = t.bank_ref "
        "WHERE t.trade_date <= ? AND t.transaction_type NOT IN (?, ?)", (as_of,) + SHORT_TYPES).fetchall()
    positions = {}
    for pair in pairs:
        basis = pair["transaction_basis"]
        if basis not in BASIS_COLUMNS:
            raise ValueError(f"account {pair['bank_ref']}: unknown transaction_basis {basis!r}")
        rows = db.execute(
            "SELECT t.* FROM tbl_transaction t "
            "JOIN tbl_transaction_type tt ON tt.transaction_type = t.transaction_type "
            "WHERE t.bank_ref=? AND t.code_ref=? AND t.trade_date<=? AND t.transaction_type NOT IN (?, ?) "
            f"ORDER BY t.{basis}, tt.priority, t.ref_num",
            (pair["bank_ref"], pair["code_ref"], as_of) + SHORT_TYPES).fetchall()
        shares, cost, _ = accumulate_position(rows)
        positions[(pair["bank_ref"], pair["code_ref"])] = (shares, cost / shares if shares else 0.0)
    return positions


def short_positions(db, as_of):
    """{(bank_ref, code_ref): (shares, average)} for every open short on as_of (shares < 0): the Short Book
    replayed in trade date and entry order, as the Short Book page does."""
    pairs = db.execute("SELECT DISTINCT bank_ref, code_ref FROM tbl_transaction_short WHERE trade_date <= ?",
                       (as_of,)).fetchall()
    positions = {}
    for pair in pairs:
        rows = db.execute(
            "SELECT * FROM tbl_transaction_short WHERE bank_ref=? AND code_ref=? AND trade_date<=? "
            "ORDER BY trade_date, ref_num", (pair["bank_ref"], pair["code_ref"], as_of)).fetchall()
        balance, _ = accumulate_short_position([{**dict(r), **{k: r[k] or 0 for k in CHARGES}} for r in rows])
        if balance < 0:
            average = get_short_average(db, pair["bank_ref"], pair["code_ref"], as_of)
            positions[(pair["bank_ref"], pair["code_ref"])] = (balance,
                                                               round(average, 4) if average is not None else 0.0)
    return positions


def shares_to_block(db, as_of):
    """{(bank_ref, code_ref): shares} still to deliver on live decumulators traded on or before as_of: daily shares
    times the days of the periods ending after as_of, doubled when geared. A period ending on or before as_of counts
    as received, flagged or not; one ending after it is still to come, flagged or not (ruling 6)."""
    to_block = {}
    contracts = db.execute(
        "SELECT ref_num, bank_ref, code_ref, daily_shares, leveraged FROM tbl_stock_contract "
        "WHERE status='active' AND transaction_type='DECU' AND trade_date<=?", (as_of,)).fetchall()
    for c in contracts:
        days = sum(_to_int(p["days"]) for p in db.execute(
            "SELECT days FROM tbl_stock_contract_period WHERE contract_ref=? AND end_date>?", (c["ref_num"], as_of)))
        shares = _to_int(c["daily_shares"]) * days * (2 if c["leveraged"] == "Yes" else 1)
        key = (c["bank_ref"], c["code_ref"])
        to_block[key] = to_block.get(key, 0) + shares
    return to_block


def live_contract_pairs(db, as_of):
    """Accounts and stocks with a live contract, accumulator or decumulator, still running after as_of."""
    return {(r["bank_ref"], r["code_ref"]) for r in db.execute(
        "SELECT DISTINCT c.bank_ref, c.code_ref FROM tbl_stock_contract c "
        "JOIN tbl_stock_contract_period p ON p.contract_ref = c.ref_num "
        "WHERE c.status='active' AND c.trade_date<=? AND p.end_date>?", (as_of, as_of))}


def closes(db, code_refs, as_of):
    """{code_ref: (price, date)}: the close on as_of, else the latest before it, as
    fixings.download_fixings.get_closing_price takes it."""
    out = {}
    for code_ref in code_refs:
        row = db.execute(
            "SELECT closing_price, trade_date FROM tbl_stock_price WHERE code_ref=? AND trade_date<=? "
            "AND closing_price IS NOT NULL ORDER BY trade_date DESC LIMIT 1", (code_ref, as_of)).fetchone()
        if row:
            out[code_ref] = (row["closing_price"], row["trade_date"])
    return out


def build_edition(db, as_of, prices=None, price_label=""):
    """Every row of the edition as of as_of. prices, {code_ref: price}, is a set supplied for this build: it wins
    over the stored closes for its codes and is never written anywhere (ruling 4)."""
    longs = long_positions(db, as_of)
    shorts = short_positions(db, as_of)
    to_block = shares_to_block(db, as_of)
    live = live_contract_pairs(db, as_of)

    keys = {pair + (LONG,) for pair, (shares, _) in longs.items() if shares}
    keys |= {pair + (LONG,) for pair in live}
    keys |= {pair + (LONG,) for pair, shares in to_block.items() if shares}
    keys |= {pair + (SHORT,) for pair in shorts}

    banks = {r["ref_num"]: r for r in db.execute(
        "SELECT ref_num, bank_id, bank_name, priority FROM tbl_bank_account")}
    codes = {r["ref_num"]: r for r in db.execute(
        "SELECT c.ref_num, c.code, c.stock_name, cur.ccy_id FROM tbl_code c "
        "LEFT JOIN tbl_currency cur ON cur.ref_num = c.ccy_ref")}
    stored = closes(db, {code_ref for _, code_ref, _ in keys}, as_of)

    rows = []
    for bank_ref, code_ref, side in keys:
        shares, average = (shorts if side == SHORT else longs).get((bank_ref, code_ref), (0, 0.0))
        if prices and code_ref in prices:
            close, close_from = prices[code_ref], price_label or "supplied"
        else:
            close, close_from = stored.get(code_ref, (None, ""))
        bank, code = banks[bank_ref], codes[code_ref]
        rows.append(EditionRow(
            bank_ref=bank_ref, bank_id=bank["bank_id"], bank_name=bank["bank_name"],
            code_ref=code_ref, code=str(code["code"]), stock_name=code["stock_name"], ccy=code["ccy_id"] or "HKD",
            side=side, shares=shares, average=average,
            to_block=to_block.get((bank_ref, code_ref), 0) if side == LONG else 0,
            close=close, close_from=close_from))
    rows.sort(key=lambda r: (banks[r.bank_ref]["priority"] or 0, r.code, r.side != LONG))
    return Edition(as_of=as_of, rows=rows,
                   price_label=(price_label or "supplied") if prices else f"closes on or before {as_of}",
                   unpriced=sorted({r.code for r in rows if r.close is None}))
```

- [ ] **Step 4: Run the harness, without and then with the evidence**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: I1 to I4 PASS, `E1, E2: not run`, `RESULT: ALL PASS`.

Run (evidence; the paths are outside the repository):
```
..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py ^
  --reference "C:\envs\assistant\products\ltv-app\app-docs\bug-reports\2026-10-30-blocked-unblocked-from-the-app\2026-10-30 Blocked Unblocked - Alvin saved 14-18.xlsm" ^
  --ledger "C:\envs\assistant\clients\ltv\backups\LTV Stocks 2026-10-30-1355.db"
```
Expected: also `I1 30 Oct ledger`, E1 and E2 PASS, and a count line for the pairs the date rule changes (the spec
expects one).

If E1 fails, find which (account, code, side) differs **without printing figures** (compare the key sets and the
count of rows whose shares differ). A key in the edition but not in the app, or the other way, is a finding to
report, not to paper over: the edition lists stocks from a fixed list, so a held stock outside it would show here.
Report it in the task report and in `BUGS.md`; do not change the comparison to hide it.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/blocked_unblocked/__init__.py ltv_app/blueprints/blocked_unblocked/edition.py scripts/verify_blocked_unblocked_edition.py
git commit -m "feat(blocked_unblocked): the edition's positions and shares to block as of a date" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Prices — the date's close, or a set supplied for one build

**Files:**
- Create: `ltv_app/blueprints/blocked_unblocked/price_set.py`
- Modify: `scripts/verify_blocked_unblocked_edition.py` (add case I5 and call it from `main`)

**Interfaces:**
- Consumes: `edition.build_edition(db, as_of, prices, price_label)`, `edition.closes(db, code_refs, as_of)`.
- Produces: `PriceSet` dataclass (`prices: dict[int, float]`, `skipped: list[str]`);
  `read_price_set(db, csv_bytes: bytes | None = None, text: str | None = None) -> PriceSet`. Task 3's view calls it.

- [ ] **Step 1: Add the failing case I5**

In the harness, add to the imports:

```python
from ltv_app.blueprints.blocked_unblocked.edition import closes
from ltv_app.blueprints.blocked_unblocked.price_set import read_price_set
```

Add these functions above `main`:

```python
def price_fingerprint(db):
    return tuple(db.execute("SELECT count(*), total(closing_price), max(ref_num) FROM tbl_stock_price").fetchone())


def case_i5(source, as_of):
    app = boot(copy_db(source))
    with app.app_context():
        db = get_db()

        def expected_close(code_ref, day):
            row = db.execute("SELECT closing_price, trade_date FROM tbl_stock_price WHERE code_ref=? AND trade_date<=? "
                             "AND closing_price IS NOT NULL ORDER BY trade_date DESC LIMIT 1", (code_ref, day)).fetchone()
            return (row[0], row[1]) if row else (None, "")

        edition = build_edition(db, as_of)
        held = [r for r in edition.rows if r.shares and r.close is not None]
        case("I5a each row is priced at the close on D, else the latest before D",
             held and all((r.close, r.close_from) == expected_close(r.code_ref, as_of) for r in edition.rows))

        target = held[0]
        last_day = db.execute("SELECT max(trade_date) FROM tbl_stock_price WHERE code_ref=? "
                              "AND closing_price IS NOT NULL", (target.code_ref,)).fetchone()[0]
        later = str((datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=1)).date())
        case("I5b a day with no close takes the latest before it",
             closes(db, [target.code_ref], later).get(target.code_ref) == expected_close(target.code_ref, last_day))

        before = price_fingerprint(db)
        supplied = build_edition(db, as_of, prices={target.code_ref: 123.45}, price_label="prices supplied (test)")
        mine = [r for r in supplied.rows if r.code_ref == target.code_ref]
        others = [r for r in supplied.rows if r.code_ref != target.code_ref]
        case("I5c a supplied price wins for its code only; the others keep their closes",
             mine and all(r.close == 123.45 and r.close_from == "prices supplied (test)" for r in mine)
             and all((r.close, r.close_from) == expected_close(r.code_ref, as_of) for r in others)
             and supplied.price_label == "prices supplied (test)")
        case("I5d a supplied price is never stored", price_fingerprint(db) == before)

        db.execute("DELETE FROM tbl_stock_price WHERE code_ref=?", (target.code_ref,))
        db.commit()
        bare = build_edition(db, as_of)
        mine = [r for r in bare.rows if r.code_ref == target.code_ref]
        case("I5e a code with no price at all has no market value and is named as unpriced",
             mine and all(r.close is None and r.market is None and r.gain is None for r in mine)
             and target.code in bare.unpriced)

        ticks = db.execute("SELECT ref_num, code, yahoo_ticker FROM tbl_code WHERE yahoo_ticker IS NOT NULL "
                           "AND yahoo_ticker != '' ORDER BY ref_num LIMIT 2").fetchall()
        header = ("Symbol,Current Price,Date,Time,Change,Open,High,Low,Volume,Trade Date,Purchase Price,"
                  "Quantity,Commission,High Limit,Low Limit,Comment\n")
        csv_bytes = (header + f"{ticks[0]['yahoo_ticker']},10.5,2026/11/06,4:08PM HKT,0,0,0,0,0,,,,,,,\n"
                     + "NOSUCH.XX,1,2026/11/06,4:08PM HKT,0,0,0,0,0,,,,,,,\n").encode("utf-8")
        text = f"{ticks[1]['code']} 1,234.50\nNOSUCH 2\nnot a price line\n"
        ps = read_price_set(db, csv_bytes, text)
        case("I5f a Yahoo CSV and pasted lines are read; what can't be read is listed",
             ps.prices == {ticks[0]["ref_num"]: 10.5, ticks[1]["ref_num"]: 1234.5} and len(ps.skipped) == 3)
```

In `main`, after `case_i4(dev, as_of)`, add:

```python
    case_i5(dev, as_of)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: `ModuleNotFoundError: No module named 'ltv_app.blueprints.blocked_unblocked.price_set'`.

- [ ] **Step 3: Write `price_set.py`**

```python
"""A price set Alvin supplies for one build of the edition.

His own prices win (ruling of 4 Nov 2026), but they are intraday quotes as often as closes, so they are used for that
build only and never written to tbl_stock_price, which the fixings and the notebook read as the day's close
(spec section 9, question 3, ruled 6 Nov)."""
import csv
import io
import re
from dataclasses import dataclass, field

LINE = re.compile(r"^([^\s,;]+)[\s,;]+(.+)$")


@dataclass
class PriceSet:
    prices: dict = field(default_factory=dict)   # code_ref -> price
    skipped: list = field(default_factory=list)  # what could not be read, as given


def _number(text):
    try:
        value = float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def read_price_set(db, csv_bytes=None, text=None):
    """Prices from a Yahoo portfolio CSV (its Symbol and Current Price columns, the file stock_price's upload reads)
    and from pasted lines of 'code price' (a comma, semicolon, tab or spaces between; the code as tbl_code has it,
    with or without its leading zeros, or its Yahoo ticker). A later entry for the same stock wins."""
    by_ticker = {str(r["yahoo_ticker"]).strip().upper(): r["ref_num"] for r in db.execute(
        "SELECT ref_num, yahoo_ticker FROM tbl_code WHERE yahoo_ticker IS NOT NULL AND yahoo_ticker != ''")}
    by_code = {}
    for r in db.execute("SELECT ref_num, code FROM tbl_code"):
        code = str(r["code"]).strip().upper()
        by_code[code] = r["ref_num"]
        if code.isdigit():
            by_code.setdefault(code.lstrip("0") or "0", r["ref_num"])

    result = PriceSet()
    if csv_bytes:
        reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig")))
        if not reader.fieldnames or "Symbol" not in reader.fieldnames or "Current Price" not in reader.fieldnames:
            result.skipped.append("the file is not a Yahoo portfolio CSV (no Symbol and Current Price columns)")
        else:
            for row in reader:
                symbol = (row.get("Symbol") or "").strip()
                ref = by_ticker.get(symbol.upper())
                price = _number(row.get("Current Price"))
                if ref is None or price is None:
                    result.skipped.append(symbol or "a row with no symbol")
                    continue
                result.prices[ref] = price

    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = LINE.match(line)
        token = match.group(1).upper() if match else ""
        ref = by_code.get(token) or by_code.get(token.lstrip("0") or "0") or by_ticker.get(token)
        price = _number(match.group(2)) if match else None
        if ref is None or price is None:
            result.skipped.append(line)
            continue
        result.prices[ref] = price
    return result
```

- [ ] **Step 4: Run the harness**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: I1 to I5f PASS, `RESULT: ALL PASS`.

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/blocked_unblocked/price_set.py scripts/verify_blocked_unblocked_edition.py
git commit -m "feat(blocked_unblocked): price the edition at the date's close or a supplied set, never stored" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: The Equities sheet and the page

**Files:**
- Create: `ltv_app/blueprints/blocked_unblocked/extensions/__init__.py`
- Create: `ltv_app/blueprints/blocked_unblocked/extensions/edition_workbook.py`
- Create: `ltv_app/blueprints/blocked_unblocked/forms.py`
- Create: `ltv_app/blueprints/blocked_unblocked/views.py`
- Create: `ltv_app/blueprints/blocked_unblocked/pages/blocked_unblocked/home.html`
- Replace: `ltv_app/blueprints/blocked_unblocked/__init__.py`
- Modify: `ltv_app/blueprints/__init__.py` (after `from . import block_unblock`)
- Modify: `ltv_app/templates/navbar.html:57` (after the `Blocked / Unblocked` link)
- Modify: `scripts/verify_blocked_unblocked_edition.py` (add case I6 and call it)
- Modify: `app/BUGS.md` (not staged)

**Interfaces:**
- Consumes: `build_edition`, `Edition`, `EditionRow` (Task 1); `read_price_set`, `PriceSet` (Task 2);
  `ltv_app.workbook_download.in_memory(wb)` and `send_workbook(output, download_name, as_attachment=True)`;
  `ltv_app.tz.ph_today`, `ph_now`; `blueprints.database.get_db`; `blueprints.auth.login_required`.
- Produces: endpoint `blocked_unblocked.home` at `/blocked-unblocked/` (GET form, POST download);
  `EditionWorkbook(edition)` with `.output` (a rewound `BytesIO`) and `.download_name`
  (`"<as_of> Blocked Unblocked.xlsx"`); sheet `Equities`, header on row 5 with the labels in `COLUMNS`, data from
  row 6. Plans B–D add their sheets to this workbook class.

- [ ] **Step 1: Add the failing case I6**

In the harness, add above `main`:

```python
def case_i6(source, as_of):
    app = boot(copy_db(source))
    client = app.test_client()
    with app.app_context():
        db = get_db()
        before = price_fingerprint(db)
        edition = build_edition(db, as_of)
    page = client.get("/blocked-unblocked/")
    response = client.post("/blocked-unblocked/", data={"report_date": as_of})
    named = f"{as_of} Blocked Unblocked.xlsx" in response.headers.get("Content-Disposition", "")
    sheet = {}
    if response.status_code == 200 and named:
        ws = load_workbook(io.BytesIO(response.data), data_only=True)["Equities"]
        col = {cell.value: i for i, cell in enumerate(ws[5])}
        for row in ws.iter_rows(min_row=6, values_only=True):
            if row[col["Account"]] is not None:
                sheet[(row[col["Account"]], row[col["Code"]], row[col["Side"]])] = row
    carried = bool(sheet) and len(sheet) == len(edition.rows) and all(
        (r.bank_id, r.code, r.side) in sheet
        and sheet[(r.bank_id, r.code, r.side)][col["Shares"]] == r.shares
        and abs(sheet[(r.bank_id, r.code, r.side)][col["Average"]] - r.average) < 1e-9
        and sheet[(r.bank_id, r.code, r.side)][col["Blocked"]] == r.blocked
        for r in edition.rows)
    case("I6a the page shows the form", page.status_code == 200 and b"Blocked Unblocked" in page.data)
    case("I6b the download is <D> Blocked Unblocked.xlsx and its Equities sheet carries every row", named and carried)

    with client.session_transaction() as sess:
        sess.pop("_flashes", None)
    client.post("/blocked-unblocked/", data={"report_date": as_of, "price_text": "NOSUCH 2"})
    with client.session_transaction() as sess:
        flashes = [message for _, message in sess.pop("_flashes", [])]
    with app.app_context():
        unchanged = price_fingerprint(get_db()) == before
    case("I6c a pasted price it can't read is reported, and no close is stored",
         any("NOSUCH" in m for m in flashes) and unchanged)
```

In `main`, after `case_i5(dev, as_of)`, add:

```python
    case_i6(dev, as_of)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: I1 to I5f PASS; I6a FAIL (404), I6b FAIL, I6c FAIL; `RESULT: FAIL`.

- [ ] **Step 3: Write the workbook**

`ltv_app/blueprints/blocked_unblocked/extensions/__init__.py`:

```python
from .edition_workbook import EditionWorkbook
```

`ltv_app/blueprints/blocked_unblocked/extensions/edition_workbook.py`:

```python
"""<date> Blocked Unblocked.xlsx. Plan A writes its data sheet, Equities: one row per account and position, every
figure the printed sheets draw on (spec section 7). The printed sheets are added by plans B to D."""
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from ....workbook_download import in_memory

SHARES = "#,##0;[Red](#,##0)"
MONEY = "#,##0.00;[Red](#,##0.00)"
PRICE = "#,##0.0000"
PERCENT = "0.00%;[Red](0.00%)"

# (header, EditionRow attribute, number format, column width)
COLUMNS = (
    ("Account", "bank_id", None, 9),
    ("Account name", "bank_name", None, 28),
    ("Code", "code", "@", 8),
    ("Stock", "stock_name", None, 26),
    ("Side", "side", None, 7),
    ("Key", "key", None, 13),
    ("Ccy", "ccy", None, 6),
    ("Shares", "shares", SHARES, 12),
    ("Average", "average", PRICE, 12),
    ("Cost", "cost", MONEY, 16),
    ("To block", "to_block", SHARES, 12),
    ("Blocked", "blocked", SHARES, 12),
    ("Unblocked", "unblocked", SHARES, 12),
    ("Short", "short", SHARES, 12),
    ("Close", "close", PRICE, 11),
    ("Close from", "close_from", None, 24),
    ("Market value", "market", MONEY, 16),
    ("Gain / Loss", "gain", MONEY, 16),
    ("Gain / Loss %", "gain_pct", PERCENT, 12),
)
HEADER_ROW = 5


class EditionWorkbook:
    def __init__(self, edition):
        self.download_name = f"{edition.as_of} Blocked Unblocked.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Equities"
        ws["A1"] = "Blocked Unblocked: Equities"
        ws["A1"].font = Font(size=14, bold=True)
        ws["A2"] = f"As of {edition.as_of}; holdings include that day's fixings"
        ws["A3"] = f"Prices: {edition.price_label}"
        for i, (header, _, _, width) in enumerate(COLUMNS, start=1):
            cell = ws.cell(HEADER_ROW, i, header)
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            ws.column_dimensions[cell.column_letter].width = width
        for r, row in enumerate(edition.rows, start=HEADER_ROW + 1):
            for i, (_, attribute, number_format, _) in enumerate(COLUMNS, start=1):
                cell = ws.cell(r, i, getattr(row, attribute))
                if number_format:
                    cell.number_format = number_format
        ws.freeze_panes = ws.cell(HEADER_ROW + 1, 1)
        self.output = in_memory(wb)
        wb.close()
```

- [ ] **Step 4: Write the form, the view, the page, and register them**

`ltv_app/blueprints/blocked_unblocked/forms.py`:

```python
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, SubmitField, TextAreaField
from wtforms.validators import DataRequired

from ...tz import ph_today


class EditionForm(FlaskForm):
    # ph_today, not ph_today(): WTForms calls it per form, so the default never freezes at server start.
    report_date = DateField(label="Edition date", validators=[DataRequired()], default=ph_today)
    price_file = FileField(label="Price set, a Yahoo portfolio CSV (optional)",
                           validators=[FileAllowed(["csv"], "A Yahoo portfolio CSV")])
    price_text = TextAreaField(label="Or paste prices, one 'code price' per line (optional)")
    submit = SubmitField(label="Generate")
```

`ltv_app/blueprints/blocked_unblocked/views.py`:

```python
from flask import Blueprint, flash, render_template

from ..auth import login_required
from ..database import get_db
from ...tz import ph_now
from ...workbook_download import send_workbook

from .edition import build_edition
from .extensions import EditionWorkbook
from .forms import EditionForm
from .price_set import read_price_set

bp = Blueprint("blocked_unblocked", __name__, template_folder="pages", url_prefix="/blocked-unblocked")


@bp.route("/", methods=["GET", "POST"])
@login_required
def home():
    form = EditionForm()
    if form.validate_on_submit():
        db = get_db()
        as_of = form.report_date.data.strftime("%Y-%m-%d")
        upload = form.price_file.data
        csv_bytes = upload.read() if upload and getattr(upload, "filename", "") else None
        text = form.price_text.data or ""

        price_set = read_price_set(db, csv_bytes, text) if (csv_bytes or text.strip()) else None
        if price_set and price_set.skipped:
            flash("Not read from the price set: " + "; ".join(price_set.skipped), category="error")
        edition = build_edition(db, as_of, prices=price_set.prices if price_set else None,
                                price_label=f"prices supplied {ph_now():%d %b %Y %H:%M}")
        if edition.unpriced:
            flash("No price for " + ", ".join(edition.unpriced) + "; their market value is left blank.",
                  category="error")
        workbook = EditionWorkbook(edition)
        return send_workbook(workbook.output, workbook.download_name)

    return render_template("blocked_unblocked/home.html", form=form)
```

`ltv_app/blueprints/blocked_unblocked/pages/blocked_unblocked/home.html`:

```html
{% extends "base.html" %}

{% block content %}
<div class="container">
    <h1>Blocked Unblocked File</h1>
    <p>The edition as of a date, built from the ledger. Holdings include that day's fixings. Prices are the date's
       close, or the latest before it, unless you supply a price set; a supplied set is used for this file only and is
       not saved as a close.</p>
    <form action="{{ url_for('blocked_unblocked.home') }}" class="form" method="post" enctype="multipart/form-data">
        {{ form.csrf_token }}
        <p>{{ form.report_date.label }} {{ form.report_date }}</p>
        <p>{{ form.price_file.label }} {{ form.price_file }}</p>
        <p>{{ form.price_text.label }}<br>{{ form.price_text(rows=6, cols=40) }}</p>
        {{ form.submit(class="btn btn-success") }}
    </form>
</div>
{% endblock %}
```

Replace `ltv_app/blueprints/blocked_unblocked/__init__.py` with:

```python
from .views import bp
```

In `ltv_app/blueprints/__init__.py`, after `from . import block_unblock`, add:

```python
from . import blocked_unblocked
```

In `ltv_app/templates/navbar.html`, after the line
`<li><a href="{{ url_for('block_unblock.home') }}">Blocked / Unblocked</a></li>`, add:

```html
                    <li><a href="{{ url_for('blocked_unblocked.home') }}">Blocked Unblocked File</a></li>
```

- [ ] **Step 5: Run the harness, then the neighbours**

Run: `..\venv\Scripts\python.exe scripts\verify_blocked_unblocked_edition.py`
Expected: every case PASS, `RESULT: ALL PASS`. Then run it again with `--reference` and `--ledger` (Task 1, Step 4).

Run the harnesses that boot every blueprint or walk the routes, to show the new blueprint breaks nothing:
`verify_auth_default_deny.py`, `verify_removed_routes.py`, `verify_route_converters.py`, `verify_launch.py`,
`verify_reports_in_memory.py`. Expected: each exits 0.

- [ ] **Step 6: Log it and commit**

In `app/BUGS.md`, in the 2026-11-02 Blocked Unblocked entry (Low), add a paragraph: plan A done
(`docs/superpowers/plans/2026-11-06-blocked-unblocked-a-edition-data.md`), the page `/blocked-unblocked/` and its
Equities sheet, the harness and its cases, the E1/E2 result and the date rule's changed-pair count, and that plans
B–D (the printed sheets) and E (the print check) follow. Do not stage `BUGS.md`.

```bash
git add ltv_app/blueprints/blocked_unblocked ltv_app/blueprints/__init__.py ltv_app/templates/navbar.html scripts/verify_blocked_unblocked_edition.py
git commit -m "feat(blocked_unblocked): a page that downloads the edition's Equities sheet as of a date" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## The plans that follow (each written when the one before it lands)

Each reads its sheets' layout afresh from the 5 Nov 16:05 edition
(`app-docs/bug-reports/2026-11-05-blocked-unblocked-rulings/`), builds from a figure-free style template
`instance/excel_templates/blocked_unblocked.xlsx` (spec section 2.3), and adds its sheets to `EditionWorkbook`.

- **B. `Blocked Unblocked`.**
  - The layout data file under `instance/` (untracked; ruling 3): the account columns, their order, labels and
    hidden state; the sections; the stock order and display names.
  - The style template's prototype rows.
  - The two halves.
  - The Python Filter Active Stocks (section 4, with F7 and F8 not reproduced).
  - The SHORT section on the BLOCKED page (F6).
  - The refusal when an account holding shares has no visible column.
  - Spec section 8, case 4.
- **C. `Market vs Average` and `Market vs Average (2)`.**
  - Rows per position key from the edition rows.
  - The bank families, with SHK Private = SHK + SHK2 (F9).
  - No edition note (F10).
  - The header naming the prices used (ruling 4).
  - A row nobody holds reads 0.
- **D. `PAGE 3` and one `PAGE 3 - <account>` page per account holding shares.**
  - F2, F3, F4.
  - The F5 totals (row 65 = SUBTOTAL(9, row 18, rows 25–63/64); row 67 = row 65 + row 16; row 7 = row 67).
  - Spec section 8, cases 3 and 7.
- **E. The print check** (`scripts/verify_blocked_unblocked_print.py`, Excel COM, read-only): spec section 8, case 6.
  - Paper, zoom, print areas, breaks, hidden columns and page counts.
  - The two PDFs, 2 and 9 pages, Legal landscape.

A ledger backup taken together with one of Alvin's editions would let plans B–E tie to an edition carrying all the
rulings. The root session is asked to take one (spec section 8, Reference edition).
