"""Regression harness: recording a bi-weekly contract warns when a period end was moved off a holiday.

A bi-weekly period ends on start + 14i - 1. When that day is a weekday holiday, CreateSchedules
moves the end to the next trading day (the v4.0.37 split rule). DB's own term sheets have ended
such periods both ways, the same holiday included (BUGS.md 2026-11-04), so the person keying
the term sheet is told which periods to check against it. On a copy of the
database, with a contract built at runtime around a weekday holiday found in tbl_holiday:
  W0 a weekday holiday with a weekday start 13 days before it was found;
  W1 CreateSchedules.holiday_rolls lists exactly the periods whose grid end is a weekday
     holiday, each with that grid end and the end it saved;
  W2 Add flashes one warning naming each of those periods with both dates;
  W3 a Monday start (every grid end a Sunday) records no holiday roll and Add flashes none;
  W4 a monthly contract records no holiday roll.
No client figure is used or printed.

Run: ../venv/Scripts/python.exe scripts/verify_holiday_roll_warning.py
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.term_sheet.models import CreateSchedules

STEP = 14
TENOR = "12m"

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, passed):
    global ok
    ok = ok and passed
    print(f"  {label}: {'PASS' if passed else 'FAIL'}")


def _d(s):
    return datetime.strptime(str(s)[:10], "%Y-%m-%d")


def _shown(s):
    return _d(s).strftime("%d-%b-%Y")


def _flashes():
    with client.session_transaction() as sess:
        return [msg for _, msg in sess.pop("_flashes", [])]


def _add(code_ref, bank_ref, start, frequency):
    form = {
        "bank_ref": bank_ref, "code_ref": code_ref, "transaction_type": "DECU",
        "trade_date": str((_d(start) - timedelta(days=1)).date()), "start_date": start,
        "daily_shares": 1000, "leveraged": "Yes", "spot": 10, "strike_rate": 105,
        "ko_rate": 95, "tenor": TENOR, "frequency": frequency, "gtd": "1m",
        "bank_doc": "", "status": "active",
    }
    _flashes()
    client.post("/term-sheet/add", data=form)
    return _flashes()


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    code_ref, ccy_ref = db.execute(
        "SELECT c.ref_num, c.ccy_ref FROM tbl_code c "
        "WHERE c.ccy_ref = (SELECT ccy_ref FROM tbl_holiday GROUP BY ccy_ref "
        "                   ORDER BY max(holi_date) DESC LIMIT 1) "
        "ORDER BY c.ref_num LIMIT 1").fetchone()
    bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account ORDER BY ref_num LIMIT 1").fetchone()[0]
    holidays = {str(r[0])[:10] for r in db.execute(
        "SELECT holi_date FROM tbl_holiday WHERE ccy_ref=?", (ccy_ref,))}

    def trading(day):
        return day.isoweekday() <= 5 and str(day.date()) not in holidays

    # A Mon-Thu holiday, so start = holiday - 13 is a Tue-Fri, and a trading day.
    holiday = next((h for h in sorted(holidays, reverse=True)
                    if _d(h).isoweekday() <= 4 and trading(_d(h) - timedelta(days=STEP - 1))), None)
    _case("W0 weekday holiday with a trading-day start found", holiday is not None)
    if holiday is None:
        sys.exit(1)
    start = str((_d(holiday) - timedelta(days=STEP - 1)).date())

    def expected_rolls(contract_ref, start_):
        rows = db.execute("SELECT end_date FROM tbl_stock_contract_period WHERE contract_ref=? "
                          "ORDER BY ref_num", (contract_ref,)).fetchall()
        out = []
        for n, row in enumerate(rows, start=1):
            grid = _d(start_) + timedelta(days=STEP * n - 1)
            if grid.isoweekday() <= 5 and str(grid.date()) in holidays:
                out.append((n, str(grid.date()), str(row[0])[:10]))
        return out

    # W1: the engine itself, on a contract ref nothing else uses.
    probe_ref = db.execute("SELECT max(ref_num) FROM tbl_stock_contract").fetchone()[0] + 1000
    ts = SimpleNamespace(ref_num=probe_ref, trade_date=str((_d(start) - timedelta(days=1)).date()),
                         start_date=start, code_ref=code_ref, tenor=TENOR,
                         frequency="bi-monthly", gtd="1m")
    schedules = CreateSchedules(ts, db)
    want = expected_rolls(probe_ref, start)
    got = list(getattr(schedules, "holiday_rolls", None) or [])
    _case("W1 holiday_rolls = the periods whose grid end is a weekday holiday",
          bool(want) and want[0][0] == 1 and [tuple(r) for r in got] == want
          and all(end != grid for _, grid, end in got))

    # W2: Add tells the person keying it.
    flashed = _add(code_ref, bank_ref, start, "bi-monthly")
    added = db.execute("SELECT max(ref_num) FROM tbl_stock_contract").fetchone()[0]
    want = expected_rolls(added, start)
    warnings = [m for m in flashed if "holiday" in m.lower()]
    _case("W2 Add flashes one warning naming each moved period and both dates",
          bool(want) and len(warnings) == 1 and warnings[0].startswith("⚠")
          and all(f"period {n} " in warnings[0] and _shown(grid) in warnings[0] and _shown(end) in warnings[0]
                  for n, grid, end in want))

    # W3: Monday start, every grid end a Sunday: a weekend roll, which is settled, is not flagged.
    monday = _d(start) - timedelta(days=_d(start).isoweekday() - 1)
    while not trading(monday):
        monday -= timedelta(days=7)
    monday = str(monday.date())
    ts_mon = SimpleNamespace(**{**vars(ts), "ref_num": probe_ref + 1, "start_date": monday,
                                "trade_date": str((_d(monday) - timedelta(days=1)).date())})
    rolls_mon = list(getattr(CreateSchedules(ts_mon, db), "holiday_rolls", ["missing"]) or [])
    flashed = _add(code_ref, bank_ref, monday, "bi-monthly")
    _case("W3 Monday start: no holiday roll recorded, no warning flashed",
          rolls_mon == [] and not [m for m in flashed if "holiday" in m.lower()])

    # W4: monthly keeps its own roll and is not flagged.
    ts_mth = SimpleNamespace(**{**vars(ts), "ref_num": probe_ref + 2, "frequency": "monthly"})
    rolls_mth = getattr(CreateSchedules(ts_mth, db), "holiday_rolls", ["missing"])
    _case("W4 monthly: no holiday roll recorded", list(rolls_mth or []) == [])

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
