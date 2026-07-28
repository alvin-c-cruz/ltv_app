"""Verification for pdf_writer.build_pdf.

Generates a real PDF against the live local DB for the same report
date/bank list used in Task 1's extraction check, confirms it's a
well-formed, non-empty PDF, and writes it out for manual visual comparison
against the user's reference printout (Sun Hung Kai Account No. 1,
27-Jul-2026, Tencent KO scenario).

Run: server/.venv/Scripts/python.exe scripts/verify_pdf_writer.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.pdf_writer import build_pdf

REPORT_DATE = date(2026, 7, 27)
BANK_IDS = ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG']
OUT_PATH = os.path.join(HERE, "_verify_pdf_writer_output.pdf")


def main():
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
        buf = build_pdf(db, REPORT_DATE, BANK_IDS)
    finally:
        ctx.pop()

    content = buf.getvalue()
    ok = True

    if not content.startswith(b"%PDF-"):
        print("FAIL: output does not start with a PDF header")
        ok = False
    else:
        print(f"PASS: valid PDF header, {len(content)} bytes")

    with open(OUT_PATH, "wb") as f:
        f.write(content)
    print(f"Wrote {OUT_PATH} -- open it manually and compare against "
          f"Dropbox/WFH/For Printing/ltv-atocks DONE and KO scenario.pdf "
          f"for the Sun Hung Kai Account No. 1 sheet (Tencent KO row, "
          f"the several 2x-accumulating ACCU rows with boxed cells).")

    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
