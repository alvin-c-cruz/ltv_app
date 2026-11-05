"""Regression harness: Refresh Periods keeps the received marks, by period number.

Refresh Periods deleted every period and rebuilt the schedule, so a contract whose fixings had
started lost its received marks, and a wrong schedule had to be corrected by hand (work order
2026-11-04). Now each received mark is put back on the period of the same number (ref_num
order), and the person is told which of those periods changed dates or no longer exist. On a
copy of the database, with a contract recorded at runtime and synthetic received figures:
  R1 refresh with nothing changed: the marks come back on the same periods with the same
     figures, no other period is marked, and no period is reported moved or dropped;
  R2 refresh after the start moves a week later: the marks stay on the same period numbers,
     and one warning names each of those periods as having changed dates;
  R3 refresh after the tenor shortens below the marked periods: the marks that fit are kept,
     and one warning names each period whose mark was dropped;
  R4 refresh of a contract with no marks: nothing is reported kept;
  R5 the confirm dialog no longer says that regenerating erases the received data.
No client figure is used or printed.

Run: ../venv/Scripts/python.exe scripts/verify_refresh_keeps_received.py
"""
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app

_db = os.path.join(tempfile.mkdtemp(), "copy.db")
shutil.copy(os.path.join(SERVER, "instance", "LTV Stocks.db"), _db)
app = create_app({"DATABASE": _db, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True
MARKED = 3


def _case(label, passed):
    global ok
    ok = ok and passed
    print(f"  {label}: {'PASS' if passed else 'FAIL'}")


def _flashes():
    with client.session_transaction() as sess:
        return [msg for _, msg in sess.pop("_flashes", [])]


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    db = get_db()
    code_ref = db.execute("SELECT ref_num FROM tbl_code WHERE ccy_ref=1 ORDER BY ref_num LIMIT 1").fetchone()[0]
    bank_ref = db.execute("SELECT ref_num FROM tbl_bank_account ORDER BY ref_num LIMIT 1").fetchone()[0]

    def periods(ref):
        return db.execute("SELECT ref_num, start_date, end_date, days, received FROM tbl_stock_contract_period "
                          "WHERE contract_ref=? ORDER BY ref_num", (ref,)).fetchall()

    def form(start, tenor):
        trade = str((datetime.strptime(start, "%Y-%m-%d") - timedelta(days=1)).date())
        return {"bank_ref": bank_ref, "code_ref": code_ref, "transaction_type": "DECU",
                "trade_date": trade, "start_date": start, "daily_shares": 1000, "leveraged": "Yes",
                "spot": 10, "strike_rate": 105, "ko_rate": 95, "tenor": tenor,
                "frequency": "bi-monthly", "gtd": "1m", "bank_doc": "", "status": "active"}

    def record(start, tenor="12m", marked=MARKED):
        client.post("/term-sheet/add", data=form(start, tenor))
        _flashes()
        ref = db.execute("SELECT max(ref_num) FROM tbl_stock_contract").fetchone()[0]
        db.execute("UPDATE tbl_stock_contract SET locked=0 WHERE ref_num=?", (ref,))
        rows = periods(ref)
        marks = {}
        for n, row in enumerate(rows[:marked], start=1):
            marks[n] = int(row["days"]) * 2000          # synthetic: days x 1000 x 2 (leveraged)
            db.execute("UPDATE tbl_stock_contract_period SET received=? WHERE ref_num=?",
                       (marks[n], row["ref_num"]))
        db.commit()
        return ref, marks, rows

    def refresh(ref, start, tenor="12m"):
        reference = db.execute("SELECT reference FROM tbl_stock_contract WHERE ref_num=?", (ref,)).fetchone()[0]
        _flashes()
        client.post(f"/term-sheet/edit/{ref}", data={**form(start, tenor), "reference": reference,
                                                      "refresh_periods": "1"})
        return _flashes()

    def marks_by_number(ref):
        return {n: int(row["received"]) for n, row in enumerate(periods(ref), start=1) if row["received"]}

    # A Tuesday start a month before the newest holiday, so the dates are real calendar days.
    start = datetime.strptime(str(db.execute("SELECT max(holi_date) FROM tbl_holiday WHERE ccy_ref=1")
                                  .fetchone()[0])[:10], "%Y-%m-%d") - timedelta(days=400)
    start += timedelta(days=(1 - start.weekday()) % 7)
    start = str(start.date())

    # R1
    ref, marks, before = record(start)
    flashed = refresh(ref, start)
    after = periods(ref)
    same_dates = [(r["start_date"], r["end_date"]) for r in after] == [(r["start_date"], r["end_date"]) for r in before]
    _case("R1 unchanged refresh: same marks on the same periods, nothing moved or dropped",
          marks_by_number(ref) == marks and same_dates and len(after) == len(before)
          and not [m for m in flashed if m.startswith("⚠") and "received" in m])

    # R2
    ref, marks, before = record(start)
    later = str((datetime.strptime(start, "%Y-%m-%d") + timedelta(days=7)).date())
    flashed = refresh(ref, later)
    warns = [m for m in flashed if m.startswith("⚠") and "changed dates" in m]
    _case("R2 start moved: marks stay by period number; one warning names each moved period",
          marks_by_number(ref) == marks and len(warns) == 1
          and all(f"period {n} " in warns[0] for n in marks))

    # R3
    ref, marks, before = record(start, marked=MARKED + 2)
    flashed = refresh(ref, start, tenor="1m")
    kept_count = len(periods(ref))
    dropped = [n for n in marks if n > kept_count]
    warns = [m for m in flashed if m.startswith("⚠") and "dropped" in m]
    _case("R3 tenor shortened: fitting marks kept; one warning names each dropped period",
          bool(dropped) and marks_by_number(ref) == {n: v for n, v in marks.items() if n <= kept_count}
          and len(warns) == 1 and all(f"period {n} " in warns[0] for n in dropped))

    # R4
    ref, marks, before = record(start, marked=0)
    flashed = refresh(ref, start)
    _case("R4 no marks: nothing reported kept",
          marks_by_number(ref) == {} and not [m for m in flashed if "received" in m.lower()])

    # R5
    ref, marks, before = record(start)
    page = client.get(f"/term-sheet/edit/{ref}").get_data(as_text=True)
    _case("R5 confirm dialog no longer says regenerating erases received data",
          "Regenerate Period Schedule?" in page and "will erase" not in page)

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
