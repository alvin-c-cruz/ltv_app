"""Verification that Model.save() parameterises ref_num instead of interpolating it.

save() puts ref_num in BOTH the parameterised SET clause and (before this fix)
an interpolated WHERE clause. The deployed schema masks the bug:
tbl_stock_contract.ref_num is INTEGER PRIMARY KEY, which rejects a non-integer
payload when it is bound to SET, so the injection dies before WHERE matters.

That protection is incidental to the column type, not intended by the code.
So this test MUST exercise a plain INTEGER column, where the bug is actually
reachable, as well as the deployed INTEGER PRIMARY KEY shape.

Never touches instance/LTV Stocks.db -- in-memory databases only.

Run: server/.venv/Scripts/python.exe scripts/verify_model_save_sql.py
"""
import os
import sqlite3
import sys
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app.blueprints.data_model import Model

PAYLOAD = "1 OR 1=1"


@dataclass
class Toy(Model):
    ref_num: int = None
    reference: str = None

    def __post_init__(self):
        self.table_name = "toy"


def fresh(coldef):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(f"CREATE TABLE toy (ref_num {coldef}, reference TEXT)")
    db.executemany("INSERT INTO toy (ref_num, reference) VALUES (?,?)",
                   [(1, "one"), (2, "two"), (3, "three")])
    db.commit()
    return db


def attack(coldef):
    """Return (outcome, rows_overwritten) for the injection payload."""
    db = fresh(coldef)
    toy = Toy(db=db)
    toy.ref_num = PAYLOAD          # what term_sheet.edit assigns from the URL
    toy.reference = "PWNED"
    try:
        toy.save()
    except Exception as exc:
        return f"raised {type(exc).__name__}", 0
    hit = db.execute("SELECT COUNT(*) c FROM toy WHERE reference='PWNED'").fetchone()["c"]
    return "completed", hit


def legitimate():
    """A normal integer update must still work and touch exactly one row."""
    db = fresh("INTEGER")
    toy = Toy(db=db)
    toy.ref_num = 2
    toy.reference = "updated"
    toy.save()
    value = db.execute("SELECT reference FROM toy WHERE ref_num=2").fetchone()["reference"]
    touched = db.execute("SELECT COUNT(*) c FROM toy WHERE reference='updated'").fetchone()["c"]
    return value, touched


failures = []

outcome, hit = attack("INTEGER")
print(f"attack / plain INTEGER       : save() {outcome}, {hit} of 3 rows overwritten")
if hit > 1:
    failures.append("injection succeeded on a plain INTEGER column -- "
                    "ref_num is still interpolated into the WHERE clause")

outcome, hit = attack("INTEGER PRIMARY KEY")
print(f"attack / INTEGER PRIMARY KEY : save() {outcome}, {hit} of 3 rows overwritten")
if hit > 1:
    failures.append("injection succeeded on an INTEGER PRIMARY KEY column")

value, touched = legitimate()
print(f"legitimate update            : ref_num=2 -> {value!r}, {touched} row(s) touched")
if value != "updated" or touched != 1:
    failures.append(f"a normal update broke: got {value!r} on {touched} row(s), "
                    "expected 'updated' on exactly 1")

if failures:
    for line in failures:
        print("FAIL:", line)
    sys.exit(1)
print("PASS")
