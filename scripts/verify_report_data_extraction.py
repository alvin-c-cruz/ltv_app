"""Before/after behavior-preservation check for the report_data.py extraction.

Generates a real workbook via build_workbook() against a FROZEN COPY of the
local DB, for a report date/bank list with real ACCU+DECU+position data, and
dumps every cell's (value, number_format) for every sheet to a deterministic
text file. Run once BEFORE a change (saves snapshot), then again AFTER
(compares against the saved snapshot) -- any diff means the change altered
behavior.

The baseline DB is frozen because the workbook renders live contract state --
remaining periods, next fixing dates, which contracts are still running --
and that moves as the client's contracts progress. Against the live DB the
snapshot drifted within weeks with no code change, so DIFFERS meant nothing
(BUGS.md 2026-09-06). The report reads today's date only when REPORT_DATE is
today, so a past REPORT_DATE on a frozen DB is fully deterministic. Regenerate
the baseline only with --freeze, which discards the old before-state; --save
after it.

Run: server/.venv/Scripts/python.exe scripts/verify_report_data_extraction.py [--freeze|--save|--check]
"""
import argparse
import os
import shutil
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)
LIVE_DB = os.path.join(SERVER, "instance", "LTV Stocks.db")
# instance/ is gitignored wholesale; scripts/ is not, so the copy stays out of it.
BASELINE_DB = os.path.join(SERVER, "instance", "_report_data_baseline.db")
SNAPSHOT_PATH = os.path.join(HERE, "_report_data_extraction_snapshot.txt")

import openpyxl

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import build_workbook

REPORT_DATE = date(2026, 7, 27)
BANK_IDS = ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG']


def snapshot_text():
    if not os.path.exists(BASELINE_DB):
        sys.exit(f"No frozen baseline at {BASELINE_DB}. Run with --freeze first.")

    app = create_app({"DATABASE": BASELINE_DB, "LOGIN_DISABLED": True})
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
        actual = db.execute("PRAGMA database_list").fetchall()[0][2]
        if os.path.abspath(actual) != os.path.abspath(BASELINE_DB):
            sys.exit(f"REFUSING: connected to {actual}, not the frozen baseline")
        buf = build_workbook(db, REPORT_DATE, BANK_IDS)
    finally:
        ctx.pop()

    wb = openpyxl.load_workbook(buf)
    lines = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lines.append(f"=== {sheet_name} ({ws.dimensions}) ===")
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    lines.append(f"{cell.coordinate}\t{cell.value!r}\t{cell.number_format}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true",
                       help="copy the live DB to the frozen baseline (discards old before-state)")
    group.add_argument("--save", action="store_true", help="save the before-snapshot")
    group.add_argument("--check", action="store_true", help="compare against the saved snapshot")
    args = parser.parse_args()

    if args.freeze:
        shutil.copy2(LIVE_DB, BASELINE_DB)
        print(f"Froze baseline: {BASELINE_DB} ({os.path.getsize(BASELINE_DB) / 1e6:.2f} MB)")
        sys.exit(0)

    text = snapshot_text()

    if args.save:
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Saved snapshot: {SNAPSHOT_PATH} ({len(text.splitlines())} lines)")
        sys.exit(0)

    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        before = f.read()
    if text == before:
        print("RESULT: IDENTICAL -- extraction is behavior-preserving.")
        sys.exit(0)
    else:
        before_lines = before.splitlines()
        after_lines = text.splitlines()
        print("RESULT: DIFFERS")
        print(f"  before: {len(before_lines)} lines, after: {len(after_lines)} lines")
        for i, (b, a) in enumerate(zip(before_lines, after_lines)):
            if b != a:
                print(f"  first diff at line {i}:\n    before: {b!r}\n    after:  {a!r}")
                break
        sys.exit(1)


if __name__ == "__main__":
    main()
