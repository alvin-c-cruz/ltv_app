"""Pin the boot-time creation of the report indexes.

The gain-loss and LTV-stocks Excel endpoints both depend on these indexes to
stay under PythonAnywhere's 300s request limit. They used to exist only as SQL
applied by hand against the live DB, so a rebuilt or restored database
regressed silently. create_app() now creates them at boot.

Asserts the structural property, not just today's list: a fresh DB built from
scratch gets every index in _REPORT_INDEXES, whatever that tuple later
contains.

Run: server/.venv/Scripts/python.exe scripts/verify_report_indexes.py
"""
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app, _REPORT_INDEXES, _ensure_report_indexes

failures = []


def check(label, ok, detail=""):
    print("%-58s %s" % (label, "PASS" if ok else "FAIL"))
    if not ok:
        failures.append("%s %s" % (label, detail))


def indexes_in(path):
    con = sqlite3.connect(path)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
    finally:
        con.close()


tmpdir = tempfile.mkdtemp(prefix="verify_idx_")

# --- 1. A DB with the real tables gets every declared index at boot ----------
db_path = os.path.join(tmpdir, "built.db")
con = sqlite3.connect(db_path)
for _, table, columns in _REPORT_INDEXES:
    cols = columns.strip("()")
    con.execute(f"CREATE TABLE {table} ({', '.join(c.strip() + ' INTEGER' for c in cols.split(','))});")
con.commit()
con.close()

create_app({"DATABASE": db_path, "LOGIN_DISABLED": True})
present = indexes_in(db_path)
for name, table, _ in _REPORT_INDEXES:
    check("created %s on %s" % (name, table), name in present,
          "-- present: %r" % sorted(present))

# --- 2. Idempotent: booting twice must not raise or duplicate ----------------
create_app({"DATABASE": db_path, "LOGIN_DISABLED": True})
check("second boot is a no-op", indexes_in(db_path) == present)

# --- 3. A missing DB must NOT be created ------------------------------------
# sqlite3.connect() on a missing path silently makes an empty file, after which
# every page fails on a missing table instead of failing loudly about the DB.
missing = os.path.join(tmpdir, "does_not_exist.db")
_ensure_report_indexes(missing)
check("missing DB is not created", not os.path.exists(missing))

create_app({"DATABASE": missing, "LOGIN_DISABLED": True})
check("create_app does not create a missing DB", not os.path.exists(missing))

# --- 4. A DB without the tables boots cleanly and makes no indexes -----------
empty = os.path.join(tmpdir, "empty.db")
sqlite3.connect(empty).close()
create_app({"DATABASE": empty, "LOGIN_DISABLED": True})
check("table-less DB boots without raising", True)
check("table-less DB gets no indexes", indexes_in(empty) == set())

# --- 5. A read-only DB must not stop the app booting ------------------------
ro = os.path.join(tmpdir, "readonly.db")
con = sqlite3.connect(ro)
con.execute("CREATE TABLE tbl_transaction (bank_ref INTEGER, code_ref INTEGER);")
con.commit()
con.close()
os.chmod(ro, 0o444)
try:
    create_app({"DATABASE": ro, "LOGIN_DISABLED": True})
    check("read-only DB boots without raising", True)
except Exception as exc:  # noqa: BLE001 -- the point is that nothing escapes
    check("read-only DB boots without raising", False, repr(exc))
finally:
    os.chmod(ro, 0o644)

print()
if failures:
    print("RESULT: %d FAILURE(S)" % len(failures))
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("RESULT: all boot-time index guarantees hold (%d indexes declared)."
      % len(_REPORT_INDEXES))
