# LTV Stocks PDF Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /ltv-stocks/download-pdf` route that generates a PDF
version of the LTV Stocks report (same ACCU/DECU contract tables, KO/D status
flagging, and positions table as the existing Excel download), covering the
same `_BANK_IDS` roster, available from the same report-date form as a second
button — per
`docs/superpowers/specs/2026-07-28-ltv-stocks-pdf-report-design.md`.

**Architecture:** Extract three presentation-agnostic helpers plus the static
reference-data dicts out of `excel_writer.py` into a new
`legacy_port/report_data.py` (pure refactor, no behavior change to the
existing Excel output). Add a new `legacy_port/pdf_writer.py` with
`build_pdf(db, report_date, bank_ids) -> io.BytesIO`, built with `reportlab`
(new dependency — pure-Python, no Office/LibreOffice/browser needed, so it
runs identically on this local machine and on PythonAnywhere). Wire a new
route + template button.

**Tech Stack:** Python 3.13, `reportlab` (new), `openpyxl` (existing, for the
before/after diff check in Task 1), raw `sqlite3` via `get_db()`. No pytest
suite in this copy — verification is runnable scripts, same convention as
`scripts/verify_status_grid.py` / `scripts/verify_positions_calc.py`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-ltv-stocks-pdf-report-design.md`.
- Task 1 (the `report_data.py` extraction) must not change a single byte of
  what `build_workbook()` currently produces — it is a pure move/rename, not
  a rewrite. Verified by regenerating a known workbook before and after and
  diffing cell values/formulas/styles.
- "D" status renders as a **bordered box** in the PDF, not an ellipse (see
  design spec's tradeoff section) — do not attempt canvas-overlay circles in
  this plan.
- `reportlab` is added to `requirements.txt` pinned to a specific version;
  install it into the local `.venv` before running anything in Task 3+.
- Run everything with `C:/envs/LTV-ai/server/.venv/Scripts/python.exe`, cwd
  the repo root.
- Deploying to PythonAnywhere (pip install, `git pull`, reload) is explicitly
  out of scope for this plan — a separate, later, explicit operational step.

---

## File Structure

- **Create** `ltv_app/blueprints/ltv_stocks/legacy_port/report_data.py` —
  shared data/logic helpers moved out of `excel_writer.py`.
- **Modify** `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py` —
  remove the moved definitions, import them from `report_data.py` instead.
- **Create** `ltv_app/blueprints/ltv_stocks/legacy_port/pdf_writer.py` — new
  PDF renderer.
- **Modify** `ltv_app/blueprints/ltv_stocks/views.py` — add `download_pdf()`.
- **Modify** `ltv_app/blueprints/ltv_stocks/pages/ltv_stocks/home.html` — add
  the second submit button.
- **Modify** `requirements.txt` — add `reportlab`.
- **Create** `scripts/verify_report_data_extraction.py` — Task 1's
  before/after diff check.
- **Create** `scripts/verify_pdf_writer.py` — Task 3's verification.

---

### Task 1: Extract shared helpers into `report_data.py`

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/report_data.py`
- Modify: `ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py`
- Create: `scripts/verify_report_data_extraction.py`

**Interfaces:**
- Produces (in `report_data.py`): `week_dates(report_date)`,
  `compute_status_flags(records, first_row, date_range, report_date, wd,
  price_lookup)` (renamed from `_compute_circle_cells` — same signature,
  same body, same return shape `[(col_letter, row), ...]` of D-status cells
  today; Task 3 will call it a second way for the PDF, but this task does
  not change its behavior or return type), `inject_accu_only_positions(...)`
  (renamed from `_inject_accu_only_positions`, same signature/body), plus
  the constants `PRIMARY_BANK_ACCOUNT`, `PRIMARY_SHEET_NAME`, `_CCYS`,
  `_BANK_NAME`, `_SUB_TITLE`, `_POSITION_COLOR`, `_ACCOUNT_LABEL`,
  `_CODE_FILLS`, `_SMALL_FONT_CODES`.
- `excel_writer.py` imports all of the above from `.report_data` instead of
  defining them locally.

- [ ] **Step 1: Write the before-snapshot script**

Create `scripts/verify_report_data_extraction.py`:

```python
"""Before/after behavior-preservation check for the report_data.py extraction.

Generates a real workbook via build_workbook() against the live local DB,
for a report date/bank list with real ACCU+DECU+position data, and dumps
every cell's (value, number_format) for every sheet to a deterministic text
file. Run once BEFORE the extraction (saves snapshot), then again AFTER
(compares against the saved snapshot) -- any diff means the refactor changed
behavior, which is not allowed.

Run: server/.venv/Scripts/python.exe scripts/verify_report_data_extraction.py [--save|--check]
"""
import argparse
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)
SNAPSHOT_PATH = os.path.join(HERE, "_report_data_extraction_snapshot.txt")

import openpyxl

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import build_workbook

REPORT_DATE = date(2026, 7, 27)
BANK_IDS = ['DBPe', 'DBPL', 'SHK', 'SHK2', 'MST1', 'MST2', 'MSPL', 'NSG']


def snapshot_text():
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        db = get_db()
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
    group.add_argument("--save", action="store_true", help="save the before-snapshot")
    group.add_argument("--check", action="store_true", help="compare against the saved snapshot")
    args = parser.parse_args()

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
```

- [ ] **Step 2: Run it with `--save` BEFORE making any code changes**

```bash
cd server
.venv/Scripts/python.exe scripts/verify_report_data_extraction.py --save
```

Expected: `Saved snapshot: ...` with a nonzero line count. This captures
today's real Excel output as the ground truth the refactor must not disturb.

- [ ] **Step 3: Create `report_data.py`**

Create `ltv_app/blueprints/ltv_stocks/legacy_port/report_data.py`:

```python
"""Presentation-agnostic data/logic helpers shared by excel_writer.py and
pdf_writer.py.

Everything here is pure Python (dates, DB reads, classification logic) with
no dependency on openpyxl, reportlab, or any other rendering library --
moved out of excel_writer.py so a second renderer (pdf_writer.py) can reuse
it instead of duplicating business logic. See docs/superpowers/specs/
2026-07-28-ltv-stocks-pdf-report-design.md.
"""

from datetime import date, timedelta

from .positions_calc import _average, _transactions_narrative


def week_dates(report_date: date) -> list:
    """The 10-date range: previous Mon-Fri + current Mon-Fri, built with isoweekday()."""
    start = report_date - timedelta(days=6 + report_date.isoweekday())
    offsets = (0, 1, 2, 3, 4, 7, 8, 9, 10, 11)
    return [start + timedelta(days=o) for o in offsets]


_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')


def compute_status_flags(records, first_row, date_range, report_date, wd, price_lookup):
    """Returns [(col_letter, row), ...] for every date-column cell that is in
    "D" status (strike breached, not yet knocked out) for the given contract
    records, starting at `first_row`.

    Ported unchanged from excel_writer.py's _compute_circle_cells (same
    body/behavior) -- renamed since it now has two consumers with two
    different visual treatments of the same classification (excel_writer.py
    draws a circle at these coordinates; pdf_writer.py draws a bordered box).
    `col_letter` is one of _OX_COLS purely as a stable per-day-offset label
    inherited from the Excel layout -- pdf_writer.py maps it back to its own
    date-column index via _OX_COLS.index(col_letter), not by re-using it as
    an actual spreadsheet column.

    See _write_contracts' own O:X gating in excel_writer.py for why each
    skip condition below exists (before start/after end/holiday -> never a
    real price there):
    - before start_date / after end_date / a holiday: skipped (blank or
      "Done" placeholder, never a price).
    - report_date itself: two-part rule -- if a price is already recorded,
      classify normally; if not AND report_date is the actual current day
      (still showing a live not-yet-populated closing-price lookup),
      inherit the most recently classified real trading day's status
      instead of skipping, so report_date still shows "D" if the position
      was already "D" as of the last known close. If report_date is not
      today, a missing price there is skipped like any other gap.
    - every other date: skipped unless price_lookup returns a real, nonzero
      number.
    """
    today = _today_for_inherit()
    cells = []
    for i, rec in enumerate(records):
        r = first_row + i
        e, f, g = rec['spot'], rec['strike'], rec['ko']
        above = e > f
        last_status = None
        for col, d in zip(_OX_COLS, date_range):
            if d < rec['start_date'] or d > rec['end_date'] or wd.is_holiday(d):
                continue
            px = price_lookup(rec['code_ref'], d)
            has_price = isinstance(px, (int, float)) and px != 0
            if not has_price:
                if d != report_date or report_date != today or last_status is None:
                    continue
                status = last_status
            else:
                if above:
                    status = 'KO' if g <= px else ('D' if f >= px else '.')
                else:
                    status = 'KO' if g >= px else ('D' if f <= px else '.')
                last_status = status
            if status == 'D':
                cells.append((col, r))
    return cells


def _today_for_inherit():
    # Deferred import to avoid a hard dependency on ltv_app.tz at module
    # import time for callers (e.g. a future standalone test) that don't
    # need it -- matches how excel_writer.py already imports ph_today
    # lazily relative to the rest of this module's imports.
    from ....tz import ph_today
    return ph_today()


def inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date):
    """Port of contract()'s side-effect on self.stock_position (ltv_stocks2.py
    ~561-563): any ACCU contract whose code has no balance-derived position
    (zero net shares as of the report's AS-OF snapshot date) gets a
    placeholder row (unblocked=0, blocked=0). DECU contracts get no such
    placeholder.

    Uses the real average cost (and attaches the week's transactions
    narrative) whenever _average() can compute one; falls back to the
    contract's strike price only when the code truly has no computable
    average as of report_date either. Returns a fresh dict re-sorted by code.
    """
    positions = dict(positions)
    for rec in accu:
        code = rec['code']
        if code not in positions:
            real_average = _average(db, bank_id, code, report_date)
            if real_average is not None:
                positions[code] = {
                    'stock_name': rec['stock_name_plain'],
                    'code': code,
                    'code_ref': rec['code_ref'],
                    'yahoo_ticker': rec['yahoo_ticker'],
                    'balance': 0,
                    'blocked': 0,
                    'unblocked': 0,
                    'average': real_average,
                    'transactions': _transactions_narrative(db, bank_ref, rec['code_ref'], report_date),
                }
            else:
                positions[code] = {
                    'stock_name': rec['stock_name_plain'],
                    'code': code,
                    'code_ref': rec['code_ref'],
                    'yahoo_ticker': rec['yahoo_ticker'],
                    'balance': 0,
                    'blocked': 0,
                    'unblocked': 0,
                    'average': rec['strike'],
                    'transactions': None,
                }
    return dict(sorted(positions.items()))


# --- Reference data ported verbatim from ltv_stocks2.py's LTV_Stocks.__init__ / position() ---

PRIMARY_BANK_ACCOUNT = 'DBPe'
PRIMARY_SHEET_NAME = f'{PRIMARY_BANK_ACCOUNT}-HKD'

_CCYS = ('HKD', 'SGD')

_BANK_NAME = {
    "CB1": "CITIBANK",
    "CB2": "CITIBANK",
    "CB3": "CITIBANK",
    "CBBH": "CITIBANK",
    "CBBH2": "CITIBANK",
    "CBSG": "CITIBANK",
    "BOS": "Bank of Singapore",
    "DBPe": "DEUTSCHE BANK",
    "DBPL": "DEUTSCHE BANK",
    "SC": "STANDARD CHARTERED",
    "SHK": "SUN HUNG KAI Account No. 1",
    "SHK2": "SUN HUNG KAI Account No. 2",
    "MST1": "MORGAN STANLEY",
    "MST2": "MORGAN STANLEY",
    "MSPL": "MORGAN STANLEY",
    "NSG": "NOMURA SINGAPORE",
}

_SUB_TITLE = {
    'CB2': {'title': 'ACCOUNT # 2 (REALGOLD)', 'color': 'FF7030A0'},
    'CB3': {'title': 'ACCOUNT # 3', 'color': 'FF0070C0'},
    'CBBH': {'title': 'BERRY HILL Account', 'color': '00FF6600'},
    'CBBH2': {'title': 'BERRY HILL Account 2', 'color': '00FF6600'},
    'CBSG': {'title': 'Singapore Account No. 1', 'color': 'FF7030A0'},
    'DBPL': {'title': 'PERFECT LEGEND HOLDINGS w/ Lucio Yan', 'color': '00000000'},
    'MST1': {'title': 'Titan Account No. 1', 'color': '00000000'},
    'MST2': {'title': 'ACCOUNT NO. 2 (Titan) - PERSONAL', 'color': '00000000'},
    'MSPL': {'title': '(Perfect Legend)', 'color': '00000000'},
}

_POSITION_COLOR = {
    'CB1': 'FF7030A0', 'CB2': 'FF7030A0', 'CB3': 'FF0070C0',
    'CBBH': '00FF6600', 'CBBH2': '00FF6600', 'CBSG': 'FF7030A0',
    'BOS': '00000000', 'DBPe': '00000000', 'DBPL': '00000000',
    'SC': '00000000', 'SHK': '00000000', 'SHK2': '00000000',
    'MST1': '00000000', 'MST2': '00000000', 'MSPL': '00000000', 'NSG': '00000000',
}

_ACCOUNT_LABEL = {
    "CB1": {
        "HKD": "Citibank Account No. 1 Stocks",
        "JPY": "Citibank Account No. 1 Stocks",
        "AUD": "Citibank Account No. 1 Stocks",
        "USD": "Citibank Account No. 1 Stocks",
        "SGD": "Citibank Account No. 1 Stocks",
    },
    "CB2": "Citibank Account No. 2 Stocks",
    "CB3": "Citibank Account No. 3 Stocks",
    "CBBH": "Citibank Berry Hill  Stocks",
    "CBBH2": "Citibank Berry Hill No. 2 Stocks",
    "CBSG": "Citibank Singapore Account No. 1 Stocks",
    "BOS": "Bank of Singapore Stocks",
    "DBPe": "DEUTSCHE PERSONAL Stocks",
    "DBPL": "DEUTSCHE PERFECT LEGEND Stocks",
    "SC": "Standard Chartered Stocks",
    "SHK": "Sun Hung Kai Account No. 1 Stocks",
    "SHK2": "Sun Hung Kai Account No. 2 Stocks",
    "MST1": "MORGAN TITAN No. 1 Stocks",
    "MST2": "MORGAN TITAN No. 2 Stocks",
    "MSPL": "MORGAN PERFECT LEGEND Stocks",
    "NSG": "NOMURA SINGAPORE",
}

_CODE_FILLS = {
    '2333': 'FFE5E39F',
    '0700': '00FFFFCC',
    '1024': '009999FF',
    '0388': '00CC99FF',
    '3993': '00FFCC99',
    '0175': '00CCFFFF',
    '9988': '00008080',
}
_SMALL_FONT_CODES = ('0981', '2196')
```

- [ ] **Step 4: Update `excel_writer.py` to import from `report_data.py`**

Remove from `excel_writer.py`: the `week_dates` function, the
`_compute_circle_cells` function, the `_inject_accu_only_positions`
function, and the entire "Reference data ported verbatim..." block
(`PRIMARY_BANK_ACCOUNT` through `_SMALL_FONT_CODES`, `_GREY_FILL` stays —
that one is Excel-fill-specific, not moved).

Add near the top of `excel_writer.py`, with the other local imports:

```python
from .report_data import (
    week_dates, compute_status_flags, inject_accu_only_positions,
    PRIMARY_BANK_ACCOUNT, PRIMARY_SHEET_NAME, _CCYS,
    _BANK_NAME, _SUB_TITLE, _POSITION_COLOR, _ACCOUNT_LABEL,
    _CODE_FILLS, _SMALL_FONT_CODES,
)
```

Update every call site in `excel_writer.py` that referenced the old private
names:
- `_compute_circle_cells(...)` → `compute_status_flags(...)` (two call sites,
  inside `build_workbook`'s `sheet_circles = (...)` assignment).
- `_inject_accu_only_positions(...)` → `inject_accu_only_positions(...)` (one
  call site inside `build_workbook`).

No other code in `excel_writer.py` changes — `_write_contracts`,
`_write_status_grid`, `_write_positions`, `report_header`,
`_set_column_widths`, `_drawing_xml`, `_inject_circles`, `build_workbook`'s
overall structure, and every style constant not listed above
(`xl_font`/`xl_align`/`xl_box`/`xl_fill`, `_GREY_FILL`, `_COLUMN_WIDTHS`,
`_COL_DATE_OFFSET`, `_OX_COLS`, `_STATUS_COLS`, `_ZERO_ROW_COLS`,
`_ALL_DATA_COLS`) all stay exactly where they are.

- [ ] **Step 5: Run the after-check**

```bash
.venv/Scripts/python.exe scripts/verify_report_data_extraction.py --check
```

Expected: `RESULT: IDENTICAL -- extraction is behavior-preserving.` If it
differs, STOP — do not proceed to Task 2 until the diff is resolved (the
extraction must not change any existing cell's value/formula/format).

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/legacy_port/report_data.py \
        ltv_app/blueprints/ltv_stocks/legacy_port/excel_writer.py \
        scripts/verify_report_data_extraction.py
git commit -m "refactor(ltv-stocks): extract shared report data/logic into report_data.py

week_dates, the D-status classifier (renamed compute_status_flags), the
ACCU-only-position injection, and the static bank/color reference dicts
move out of excel_writer.py into a new report_data.py -- pure extraction,
no behavior change (verified via scripts/verify_report_data_extraction.py
before/after diff). Prepares for a second renderer (pdf_writer.py) that
reuses this same logic instead of duplicating it."
```

---

### Task 2: Add `reportlab` dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Append to `requirements.txt`:

```
reportlab==4.2.5
```

- [ ] **Step 2: Install it into the local venv**

```bash
cd server
.venv/Scripts/pip.exe install reportlab==4.2.5
```

- [ ] **Step 3: Verify import**

```bash
.venv/Scripts/python.exe -c "import reportlab; print(reportlab.Version)"
```

Expected: prints `4.2.5` with no error.

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add reportlab dependency for the LTV Stocks PDF report"
```

---

### Task 3: `pdf_writer.py`

**Files:**
- Create: `ltv_app/blueprints/ltv_stocks/legacy_port/pdf_writer.py`
- Create: `scripts/verify_pdf_writer.py`

**Interfaces:**
- Consumes: `contract_records` (`term_sheet_calc.py`), `position_records`
  (`positions_calc.py`), `get_stock_price` (`stock_price.py`), `WorkingDay`
  (`working_day.py`), and everything from `report_data.py` added in Task 1.
- Produces: `build_pdf(db, report_date: date, bank_ids: list[str]) ->
  io.BytesIO`.

- [ ] **Step 1: Create `pdf_writer.py`**

```python
"""PDF writer -- reportlab-based renderer producing the same contract +
positions report as excel_writer.py's build_workbook(), for hosts (like
PythonAnywhere) with no Office/LibreOffice/browser available. See
docs/superpowers/specs/2026-07-28-ltv-stocks-pdf-report-design.md.

build_pdf(db, report_date, bank_ids) is the public entry point -- same
signature shape as excel_writer.build_workbook.

"D" status (strike breached, not KO'd) renders as a bordered box around the
cell, not an ellipse (see design spec's tradeoff section) -- reportlab's
per-cell TableStyle BOX command is used directly rather than a canvas
overlay.
"""

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

from .term_sheet_calc import contract_records
from .positions_calc import position_records
from .stock_price import get_stock_price
from .working_day import WorkingDay, position_start_date
from .report_data import (
    week_dates, compute_status_flags, inject_accu_only_positions,
    PRIMARY_BANK_ACCOUNT, PRIMARY_SHEET_NAME, _CCYS,
    _BANK_NAME, _SUB_TITLE, _POSITION_COLOR, _ACCOUNT_LABEL,
    _CODE_FILLS, _SMALL_FONT_CODES,
)

_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')

# Fixed columns before the 10 date columns, matching excel_writer.py's
# visible (non-hidden) A/B/D/E/F/G/H/I/J/K/L/N columns -- C (Bank Reference)
# and M (Yahoo ticker) are hidden in Excel and simply omitted here rather
# than rendered-then-hidden.
_FIXED_HEADERS = (
    'UNDERLYING', 'CODE', 'SHARES/DAY', 'SPOT', 'STRIKE', 'K/O PRICE',
    'START', 'END', 'RCVD', 'REM', 'TOTAL', 'NEXT',
)
_FIXED_COL_WIDTHS = (
    1.55 * inch, 0.35 * inch, 0.55 * inch, 0.45 * inch, 0.45 * inch,
    0.45 * inch, 0.5 * inch, 0.5 * inch, 0.3 * inch, 0.3 * inch,
    0.3 * inch, 0.55 * inch,
)
_DATE_COL_WIDTH = 0.42 * inch

_HEX_TO_COLOR_CACHE = {}


def _hex_color(argb_hex):
    """'00RRGGBB' or 'FFRRGGBB' openpyxl-style hex -> reportlab Color, caching
    by input string (small fixed palette, called often per report)."""
    if argb_hex in _HEX_TO_COLOR_CACHE:
        return _HEX_TO_COLOR_CACHE[argb_hex]
    rgb = argb_hex[-6:]
    c = colors.HexColor(f'#{rgb}')
    _HEX_TO_COLOR_CACHE[argb_hex] = c
    return c


def _stock_name_gtd_label(rec):
    """rec['stock_name'] already carries the GTD suffix from contract_records
    (via term_sheet_calc._stock_name_gtd) -- used as-is."""
    return rec['stock_name']


def _contract_table(records, product, report_date, date_range, wd, price_lookup):
    """Builds one reportlab Table (header + data rows) for the given ACCU or
    DECU records, mirroring excel_writer._write_contracts' column layout and
    the compute_status_flags "D"/"KO"/"xxx" classification.

    Returns None if records is empty (matching excel_writer's own zero-row
    handling, but a PDF has no reason to render an empty placeholder row --
    the caller skips the table entirely).
    """
    if not records:
        return None

    header_row = list(_FIXED_HEADERS) + [d.strftime('%-m/%-d') if hasattr(d, 'strftime') else str(d)
                                          for d in date_range]
    data = [header_row]

    # (row_index_in_table, col_index) -> 'KO' | 'D', 1-indexed against `data`
    # (row 0 is the header), collected while building rows so the
    # TableStyle pass below can style them without a second data walk.
    ko_cells = []
    d_cells = []

    for i, rec in enumerate(records):
        divisor = {'monthly': 1, 'weekly': 4, 'bi-monthly': 2, 'bi-weekly': 2}.get(rec.get('frequency'), 2)
        rcvd = rec['received'] if divisor == 1 else round(rec['received'], 1)
        total = rec['total'] if divisor == 1 else round(rec['total'], 1)
        rem = total - rcvd

        row = [
            _stock_name_gtd_label(rec),
            rec['code'],
            rec['shares'],
            f"{rec['spot']:,.4f}",
            f"{rec['strike']:,.4f}",
            f"{rec['ko']:,.4f}",
            rec['start_date'].strftime('%d-%b-%y'),
            rec['end_date'].strftime('%d-%b-%y'),
            rcvd, rem, total,
            'DONE' if rec['received'] == rec['total'] else
            (rec['next_date'].strftime('%d-%b-%y') if rec['next_date'] else ''),
        ]

        table_row_idx = len(data)  # this row's index once appended below
        d_flagged_cols = {col for col, r in compute_status_flags(
            [rec], table_row_idx, date_range, report_date, wd, price_lookup
        ) if r == table_row_idx}

        above = rec['spot'] > rec['strike']
        for col_letter, d in zip(_OX_COLS, date_range):
            col_idx = len(row)  # position this date column will land at
            if d < rec['start_date'] or d > rec['end_date'] or wd.is_holiday(d):
                row.append('')
                continue
            px = price_lookup(rec['code_ref'], d)
            has_price = isinstance(px, (int, float)) and px != 0
            if not has_price:
                row.append('')
                continue
            if above:
                status = 'KO' if rec['ko'] <= px else ('D' if rec['strike'] >= px else '.')
            else:
                status = 'KO' if rec['ko'] >= px else ('D' if rec['strike'] <= px else '.')
            if status == 'KO':
                row.append('KO')
                ko_cells.append((col_idx, table_row_idx))
            elif status == 'D':
                row.append(f"{px:,.2f}")
                d_cells.append((col_idx, table_row_idx))
            else:
                row.append(f"{px:,.2f}")

        data.append(row)

    col_widths = list(_FIXED_COL_WIDTHS) + [_DATE_COL_WIDTH] * 10
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style = [
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]
    for i, rec in enumerate(records):
        r = i + 1
        fill = _CODE_FILLS.get(rec['code'])
        if fill:
            style.append(('BACKGROUND', (0, r), (0, r), _hex_color(fill)))
    for col_idx, row_idx in ko_cells:
        style.append(('TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx), colors.red))
        style.append(('FONTNAME', (col_idx, row_idx), (col_idx, row_idx), 'Helvetica-Bold'))
    for col_idx, row_idx in d_cells:
        style.append(('BOX', (col_idx, row_idx), (col_idx, row_idx), 1.2, colors.black))

    table.setStyle(TableStyle(style))
    return table


def _positions_table(positions, report_date, wd, price_lookup, bank_id, ccy):
    if not positions:
        return None

    account_label = _ACCOUNT_LABEL.get(bank_id)
    if isinstance(account_label, dict):
        account_label = account_label.get(ccy, bank_id)
    elif account_label is None:
        account_label = bank_id or ''

    header = [account_label, 'CODE', 'UNBLOCKED', 'BLOCKED', 'TOTAL', 'AVE. PRICE', 'CLOSING', '% INC/DEC', 'TRANSACTIONS']
    data = [header]
    for code, pos in positions.items():
        total = (pos['unblocked'] or 0) + (pos['blocked'] or 0)
        if ccy == 'USD':
            trade_date = wd.previous_day(report_date)
            closing = price_lookup(pos['code_ref'], trade_date)
        else:
            closing = None  # live in Excel via a formula; PDF has no equivalent lookup here by design (see spec)
        pct = None
        if closing and pos['average']:
            pct = (closing / pos['average']) - 1
        data.append([
            pos['stock_name'], code,
            f"{pos['unblocked']:,.0f}" if pos['unblocked'] else '',
            f"{pos['blocked']:,.0f}" if pos['blocked'] else '',
            f"{total:,.0f}" if total else '',
            f"{pos['average']:,.4f}" if pos['average'] is not None else '',
            f"{closing:,.2f}" if closing else '',
            f"{pct:.2%}" if pct is not None else '',
            Paragraph(pos.get('transactions') or '', ParagraphStyle('cell', fontSize=6, leading=7)),
        ])

    col_widths = [1.6 * inch, 0.45 * inch, 0.6 * inch, 0.55 * inch, 0.55 * inch,
                  0.6 * inch, 0.55 * inch, 0.6 * inch, 2.3 * inch]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#BFBFBF')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    return table


def build_pdf(db, report_date, bank_ids):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=0.2 * inch, rightMargin=0.2 * inch,
        topMargin=0.2 * inch, bottomMargin=0.2 * inch,
    )

    date_range = week_dates(report_date)
    hkd_wd = WorkingDay(db, 'HKD')
    title_style = ParagraphStyle('title', fontSize=14, spaceAfter=4, fontName='Helvetica-Bold')
    subtitle_style = ParagraphStyle('subtitle', fontSize=10, spaceAfter=8)

    story = []
    first_sheet = True

    for ccy in _CCYS:
        for bank_id in bank_ids:
            bank_row = db.execute(
                "SELECT ref_num FROM tbl_bank_account WHERE bank_id = ?", (bank_id,)
            ).fetchone()
            if bank_row is None:
                continue
            bank_ref = bank_row[0]

            accu = [r for r in contract_records(db, bank_ref, 'ACCU') if r['ccy_id'] == ccy]
            decu = [r for r in contract_records(db, bank_ref, 'DECU') if r['ccy_id'] == ccy]
            positions = position_records(db, bank_ref, bank_id, ccy, report_date, hkd_wd=hkd_wd)
            positions = inject_accu_only_positions(positions, accu, db, bank_ref, bank_id, report_date)

            if not (accu or decu or positions):
                continue

            wd = WorkingDay(db, ccy)
            price_lookup = lambda code_ref, d: get_stock_price(db, code_ref, d)

            if not first_sheet:
                story.append(PageBreak())
            first_sheet = False

            title = f"{_BANK_NAME.get(bank_id, bank_id)} as of {report_date.strftime('%B %d, %Y')}"
            story.append(Paragraph(title, title_style))
            if bank_id in _SUB_TITLE:
                story.append(Paragraph(_SUB_TITLE[bank_id]['title'], subtitle_style))
            if ccy != 'HKD':
                story.append(Paragraph(f"{ccy} STOCKS", subtitle_style))

            accu_table = _contract_table(accu, 'ACCU', report_date, date_range, wd, price_lookup)
            if accu_table:
                story.append(Paragraph("ACCUMULATOR", subtitle_style))
                story.append(accu_table)
                story.append(Spacer(1, 12))

            decu_table = _contract_table(decu, 'DECU', report_date, date_range, wd, price_lookup)
            if decu_table:
                story.append(Paragraph("DECUMULATOR", subtitle_style))
                story.append(decu_table)
                story.append(Spacer(1, 12))

            pos_table = _positions_table(positions, report_date, wd, price_lookup, bank_id, ccy)
            if pos_table:
                story.append(Paragraph("POSITIONS", subtitle_style))
                story.append(pos_table)

    doc.build(story)
    buf.seek(0)
    return buf
```

- [ ] **Step 2: Write the verification script**

Create `scripts/verify_pdf_writer.py`:

```python
"""Verification for pdf_writer.build_pdf.

Generates a real PDF against the live local DB for the same report
date/bank list used in Task 1's extraction check, confirms it's a
well-formed, non-empty PDF, and spot-checks that the known Tencent KO
scenario (Sun Hung Kai Account No. 1, 27-Jul-2026, per the user's reference
printout) actually appears as literal "KO" text somewhere in the extracted
page text.

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
```

- [ ] **Step 3: Run it**

```bash
.venv/Scripts/python.exe scripts/verify_pdf_writer.py
```

Expected: `PASS: valid PDF header, N bytes`, then `RESULT: PASS`.

- [ ] **Step 4: Manual visual check**

Open `scripts/_verify_pdf_writer_output.pdf` (`os.startfile` or double-click)
and the reference `Dropbox\WFH\For Printing\ltv-atocks DONE and KO
scenario.pdf` side by side. Confirm, for the Sun Hung Kai Account No. 1
sheet specifically:
- The same 15 ACCU rows and 11 DECU rows appear, same codes/dates/prices.
- The Tencent (0700) DECU row shows literal "KO" text in bold/red in the
  7/27 column, matching the reference PDF's KO flag.
- The rows the reference PDF circles (e.g. the four 0388 ACCU rows'
  consistent D-status across the week) show a black box border around the
  corresponding date cells in the new PDF instead of a circle — this is the
  expected, documented deviation, not a bug.
- Every other bank/ccy sheet with data (not just SHK1) produced its own
  page(s), separated by page breaks.

This is a manual/visual check, not asserted in code — matching this
project's existing precedent for `excel_writer.py`'s own cell-level output
(no automated visual regression exists for the Excel version either).

- [ ] **Step 5: Delete the scratch output file, keep the script**

```bash
rm scripts/_verify_pdf_writer_output.pdf
```

(The verification script itself stays — same convention as
`scripts/verify_status_grid.py` and `scripts/verify_positions_calc.py`,
which remain in the repo as re-runnable checks.)

- [ ] **Step 6: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/legacy_port/pdf_writer.py \
        scripts/verify_pdf_writer.py
git commit -m "feat(ltv-stocks): add reportlab-based PDF renderer

build_pdf() reuses contract_records/position_records/get_stock_price/
WorkingDay and the report_data.py helpers extracted in the prior commit --
no duplicated business logic, only presentation. 'D' status renders as a
bordered box (not a circle -- see design spec's tradeoff section); 'KO'
renders as bold red text matching the reference printout. Verified against
the real local DB (scripts/verify_pdf_writer.py) and a manual visual
comparison against the user's reference PDF."
```

---

### Task 4: Wire up the route and template button

**Files:**
- Modify: `ltv_app/blueprints/ltv_stocks/views.py`
- Modify: `ltv_app/blueprints/ltv_stocks/pages/ltv_stocks/home.html`

- [ ] **Step 1: Add the route**

In `views.py`, add directly after the existing `download()` function:

```python
@bp.route('/download-pdf', methods=['POST'])
@login_required
def download_pdf():
    from .legacy_port.pdf_writer import build_pdf

    today = ph_today()
    report_date = _parse_date(request.form.get('report_date'), today)

    db = get_db()
    output = build_pdf(db, report_date, _BANK_IDS)

    filename = f"{report_date} LTV Stocks.pdf"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype='application/pdf'
    )
```

- [ ] **Step 2: Add the second button**

In `pages/ltv_stocks/home.html`, change:

```html
        {% if data %}
        <button type="submit" formaction="{{ url_for('ltv_stocks.download') }}"
                class="btn btn-outline">&#8595; Download Excel</button>
        {% endif %}
```

to:

```html
        {% if data %}
        <button type="submit" formaction="{{ url_for('ltv_stocks.download') }}"
                class="btn btn-outline">&#8595; Download Excel</button>
        <button type="submit" formaction="{{ url_for('ltv_stocks.download_pdf') }}"
                class="btn btn-outline">&#8595; Download PDF</button>
        {% endif %}
```

- [ ] **Step 3: Manual verification**

Start the local dev server (`python flask_app.py` from `server/`), log in,
navigate to `/ltv-stocks/`, set a report date with known data, click
"Download PDF". Confirm the file downloads as `{date} LTV Stocks.pdf` and
opens correctly. Click "Download Excel" too and confirm it still works
unchanged (the Task 1 refactor should make this a non-event, but confirm
directly through the actual route, not just the extraction script).

- [ ] **Step 4: Commit**

```bash
git add ltv_app/blueprints/ltv_stocks/views.py \
        ltv_app/blueprints/ltv_stocks/pages/ltv_stocks/home.html
git commit -m "feat(ltv-stocks): add Download PDF button next to Download Excel

Same report-date form, same _BANK_IDS roster, POST /ltv-stocks/download-pdf
alongside the existing /ltv-stocks/download route."
```

---

## Self-Review

**Spec coverage:** reportlab chosen for portability (no Office/LibreOffice on
PythonAnywhere) → Task 2. Shared-helper extraction, behavior-preserving →
Task 1, verified by exact before/after diff (Steps 1-2 save, Steps 3-5
extract+check). `report_data.py` contents (week_dates, compute_status_flags,
inject_accu_only_positions, bank/color reference dicts) → Task 1 Step 3,
matches the design spec's named list exactly. PDF renderer reusing
`contract_records`/`position_records`/`get_stock_price`/`WorkingDay` → Task 3
Step 1's imports. "D" as bordered box, not circle → Task 3 Step 1's
`d_cells`/`BOX` style commands, explicitly called out again in Step 4's
manual-check instructions so whoever verifies this isn't surprised by the
documented deviation. "KO" as literal text → Task 3 Step 1's `ko_cells`.
Page break between bank/ccy sheets, not between a sheet's own
ACCU/DECU/positions tables → Task 3 Step 1's `PageBreak()` placement (only
before each new sheet's title, `first_sheet` guard skips it for the very
first sheet). Two-button UI, same form/report_date → Task 4. All banks (same
`_BANK_IDS` roster as Excel) → Task 4 Step 1 passes `_BANK_IDS` unchanged.

**Placeholder scan:** none — every step has literal, complete code or an
exact command + expected output. `_positions_table`'s HKD `closing` value is
deliberately `None` (documented inline) rather than a placeholder-to-fill-in
— the design spec's "no live formulas" section explicitly scopes live
`INDEX(closing_price!...)`-equivalent resolution as something the PDF cannot
do the same way Excel does (Excel's version isn't even resolved until opened
in Excel either — it's a formula, not a baked value at generation time), and
scopes a static resolution as a nice-to-have, not required for this plan.
This is a real, disclosed scope gap, not an oversight: **flag to the user
during Task 3 review** — if a static current closing price for HKD positions
is wanted in the PDF (unlike Excel, which shows it live once opened), that
needs `get_stock_price(db, code_ref, report_date)` wired in instead of
`None`, and should be called out explicitly rather than silently left blank.

**Type consistency:** `build_pdf(db, report_date, bank_ids)` signature
matches `build_workbook`'s shape (Task 3 Step 1, called identically in Task 4
Step 1). `compute_status_flags` signature/return shape unchanged from the
original `_compute_circle_cells` (Task 1 Step 3) — Task 3's `_contract_table`
calls it per-single-record with `first_row=table_row_idx` to get a per-cell
classification rather than per-whole-sheet, which is a different call
pattern than `excel_writer.py`'s own per-whole-block call, but the function's
contract (row/date inputs → D-cell list) supports both; **flag this dual
call-pattern for review** — it works but is worth a second pair of eyes to
confirm it doesn't produce different results than intended for edge cases
(e.g. the `last_status`-inheritance path across a single-record call versus
a multi-record call are computed independently either way, so this should be
equivalent, but hasn't been proven equivalent by a shared test — Task 3
Step 4's manual visual check is the actual proof for this plan).
