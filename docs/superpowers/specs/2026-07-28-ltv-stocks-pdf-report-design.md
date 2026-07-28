# LTV Stocks PDF report — design

Date: 2026-07-28
Status: Proposed, pending review

## Context

The `/ltv-stocks/` page (`ltv_app/blueprints/ltv_stocks/`) generates an Excel
workbook (`build_workbook()` in `legacy_port/excel_writer.py`) — one sheet per
bank/currency combination, each with an ACCU contracts table, a DECU contracts
table, a 10-day closing-price grid with live KO/D-status formulas (circled
cells for "D" = strike breached without knocking out), and a stock-positions
table. See `docs/superpowers/specs/2026-07-17-status-ko-tracking-grid-design.md`
for that grid's own history.

The user prints this workbook to PDF today by hand (confirmed via
`Dropbox\WFH\For Printing\ltv-atocks DONE and KO scenario.pdf`, a manual
Excel→PDF export of the Sun Hung Kai Account No. 1 sheet, generated to
highlight a knocked-out Tencent decumulator and several 2x-accumulating
contracts). The user wants **the app itself** to produce this PDF, in the same
visual style as that reference file, for **all banks** (the same `_BANK_IDS`
roster the Excel download already covers — `DBPe, DBPL, SHK, SHK2, MST1, MST2,
MSPL, NSG`), generated **at the same time** the Excel workbook is (i.e.
available from the same report-date form, not a separate disconnected step).

## Deployment constraint driving the approach

Production (`larrylilia.pythonanywhere.com`) is the system where this actually
gets used daily. It is a Linux host with **no Microsoft Excel, no LibreOffice/
`soffice`, and no browser binaries installed** (this workspace's local machine
happens to have Excel, but that's irrelevant — the app must work identically
wherever it's deployed, and PythonAnywhere hosting doesn't allow installing
Office or arbitrary system packages). This rules out:

- Converting the generated `.xlsx` to PDF via Excel/LibreOffice automation
  (no such binary exists on the server to shell out to).
- An HTML→PDF renderer that needs a real browser (Playwright/Chromium) — heavy
  to install and run reliably on PythonAnywhere's account tiers, and this app
  has no existing browser-rendering dependency to build on (the `email-analysis`
  skill's Playwright usage is a separate, local-only admin workspace, not part
  of this Flask app's own dependencies).

**Decision: use `reportlab`**, a pure-Python PDF-generation library (no
external binary, no browser, no system package requirement) — new dependency,
added to `requirements.txt`. This runs identically on Windows (local `ltv_app`)
and PythonAnywhere's Linux hosting.

## Architecture: extract the shared data/logic layer first

`excel_writer.py` already keeps almost all business logic separate from
openpyxl specifics — `contract_records()`, `position_records()`,
`get_stock_price()`, and `WorkingDay` (in `term_sheet_calc.py`,
`positions_calc.py`, `stock_price.py`, `working_day.py` respectively) are pure
data functions with no openpyxl dependency. But a few small helpers **inside**
`excel_writer.py` are also presentation-agnostic and would otherwise have to be
duplicated for a second renderer:

- `week_dates(report_date)` — the 10-date range.
- `_compute_circle_cells(...)` — computes, in pure Python, which (contract row,
  date column) cells are in "D" status (strike breached, not KO'd). Today this
  exists only to know where to draw circles in the Excel output (openpyxl can't
  evaluate its own KO/D formulas, so this recomputes the same test for circle
  placement). A PDF renderer needs the exact same classification.
- `_inject_accu_only_positions(...)` — the ACCU-only-position placeholder-row
  injection logic (real average cost if computable, else strike price
  fallback).

**Move these three functions (unchanged) into a new module,
`legacy_port/report_data.py`.** `excel_writer.py` imports them from there
instead of defining them locally; the new `pdf_writer.py` imports the same
functions. No behavior change to the Excel output — this is a pure
extraction/rename, not a rewrite. (`_compute_circle_cells` is renamed to
`compute_status_flags` since its result is now consumed by two different
renderers with two different visual treatments for the same classification —
see below — and the leading underscore no longer fits a function used outside
its original module.)

Everything else specific to *how* a cell/table looks (fonts, fills, borders,
column widths, page setup, circles-vs-boxes) stays local to each renderer.

## New module: `legacy_port/pdf_writer.py`

Public entry point, matching `excel_writer.py`'s shape:

```python
def build_pdf(db, report_date: date, bank_ids: list[str]) -> io.BytesIO
```

Built with `reportlab.platypus` (`SimpleDocTemplate`, `Table`, `TableStyle`,
`Paragraph`, `PageBreak`, `Spacer`), landscape A4 — matching
`excel_writer.py`'s own `paper_size=4, orientation='landscape'`.

### Per-sheet content, one call per (ccy, bank_id) pair with any ACCU/DECU/position data

Same iteration `build_workbook()` already does (`for ccy in _CCYS: for bank_id
in bank_ids:`), same skip condition (`if not (accu or decu or positions):
continue`), same `_inject_accu_only_positions` call — this loop structure
moves into `pdf_writer.py` largely as-is, swapping openpyxl calls for
Platypus flowables.

- **Report header** — bank name + "as of {date}" title, matching
  `report_header()`'s per-bank sub-title/color logic (`_SUB_TITLE`,
  `_POSITION_COLOR` dicts, moved into `report_data.py` alongside the bank
  reference tables `_BANK_NAME`/`_ACCOUNT_LABEL` — these are plain data, not
  openpyxl-specific, so they belong in the shared module too).
- **ACCU table**, then **DECU table** — one `reportlab.platypus.Table` each,
  columns matching the Excel layout: Underlying / Code / Bank Reference /
  Shares-per-Day / Spot / Strike / KO Price / Start / End / Rcvd-Rem-Total
  months / Date of next Accu-or-Decu / 10-day closing-price columns. Per-code
  background fill on the underlying-name cell (`_CODE_FILLS`, moved to
  `report_data.py`). "DONE" text replaces the "next date" cell when
  `received == total`, matching `_write_contracts`.
- **Status flagging in the closing-price columns** (this is the visual core of
  what the user's reference PDF is for):
  - **"KO"** — when `compute_status_flags` (see above) classifies a cell as
    knocked out, write the literal text `"KO"` in that date's cell instead of
    the price, bold — matching the reference PDF's Tencent row exactly (page
    2, 7/27 column).
  - **"D"** (strike breached, not KO'd) — draw a **rectangular box border**
    around that specific cell (via a per-cell `TableStyle` `BOX` command
    targeting that cell's `(col, row)` coordinates), rather than an ellipse.
    **This is a deliberate deviation from the Excel version's circle** —
    reportlab's `Table`/`TableStyle` can style individual cell borders
    directly with no extra drawing-layer complexity, whereas a true ellipse
    would need a raw canvas overlay positioned against the table's computed
    cell geometry (`Table.wrap()` results), which is fragile against dynamic
    row heights/column widths from real data. A bordered box communicates the
    same "flagged" meaning. **Flag this specific tradeoff to the user during
    review** — if an actual circle is a hard requirement (not just "same
    information, similar look"), the canvas-overlay approach is the fallback
    and should be scoped as follow-up work, not blocking this design.
  - `"xxx"` (price is 0/placeholder) and `""` (no data yet) — render exactly
    as in Excel: literal `"xxx"` text, or a blank cell.
  - Grey-fill cells before `start_date` / after `end_date` (matching Excel's
    `_GREY_FILL`) via the same per-cell background-color styling.
- **Positions table** — same columns as `_write_positions` (stock name, code,
  unblocked/blocked/total shares, average price, closing price, %inc/dec,
  transactions narrative), per-bank font color.
- **Page breaks**: force a new page **between bank/ccy sheets** (`PageBreak()`
  after each sheet's content), matching "one bank's report starts fresh."
  **Do not** force a break between a sheet's ACCU table, DECU table, and
  positions table — let Platypus's natural table pagination flow, the same
  way printing the Excel sheet naturally split ACCU onto page 1 and DECU onto
  page 2 in the reference file (that split was a consequence of row count
  against the page size, not a deliberate per-table page boundary — a sheet
  with fewer contracts should NOT force an artificial page break just because
  today's SHK1 example happened to need one).
- **No live formulas** — a PDF is static, so unlike Excel's `=INDEX(...)`
  closing-price lookups (which recalculate if the underlying `closing_price`
  sheet changes later), the PDF renders the resolved price value at
  generation time via the same `get_stock_price()` lookup Excel uses. No
  cross-sheet total formulas either (Excel's ACCU/DECU count `=SUM(...)`
  across sheets) — if a portfolio-wide total is wanted in the PDF, compute it
  in Python and print it as a static number; **out of scope for v1** unless
  requested.

### What's explicitly NOT ported

- The Excel version's off-print-area `Z:AJ` helper-formula columns — those
  exist so the grid recalculates live in Excel; a PDF has no live
  recalculation, so `compute_status_flags` is called once in Python and its
  result baked directly into the rendered cell (text/border/fill), with no
  equivalent hidden-column concept needed.
- Column-level hidden columns (`C`, `M` hidden in Excel for Bank
  Reference/Yahoo ticker) — simply omit those columns from the PDF table
  entirely rather than rendering-then-hiding.

## New route

Add `POST /ltv-stocks/download-pdf` to `views.py`, mirroring `download()`:

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
    return send_file(output, download_name=filename, as_attachment=True,
                      mimetype='application/pdf')
```

`pages/ltv_stocks/home.html` gets a second submit button next to "Download
Excel", same form, same `report_date` field, `formaction` pointing at the new
route — satisfying "generate it as we generate the excel file" (one form,
one report-date, both downloads available at the same moment) without
requiring a single response to somehow return two files. **This two-button
approach is the assumed answer to "how does the user get both" — flag during
review if a single click producing both files (e.g. a zip) is actually
wanted instead.**

## Verification

No test suite exists in this repo. Verification, matching this session's
established approach for `ltv_stocks`-area work:

1. Generate the PDF against the real local DB for a report date with known
   ACCU/DECU/position data (e.g. re-derive the same Sun Hung Kai Account No. 1,
   27-Jul-2026 scenario the reference PDF captures) and manually compare every
   contract row's figures, the Tencent "KO" cell, and every circled-in-Excel
   "D" cell against its boxed equivalent in the new PDF.
2. Spot-check a sheet with only ACCU, only DECU, and only positions (no
   contracts) to confirm the skip-when-empty logic still holds and page
   breaks land in sensible places.
3. Confirm the extraction into `report_data.py` didn't change the *existing*
   Excel output — regenerate a known-good `.xlsx` before and after the
   refactor and diff cell values/formulas/styles (openpyxl `load_workbook`,
   compare sheet-by-sheet) to prove the extraction was behavior-preserving.

## Out of scope

- True ellipse/circle rendering for "D" status (see tradeoff above) — v1 uses
  a bordered box.
- A combined single-response (e.g. zip) download of both files.
- Cross-sheet portfolio totals in the PDF.
- Any change to the underlying data functions (`contract_records`,
  `position_records`, `get_stock_price`, `WorkingDay`) — this design only
  extracts three presentation-agnostic helpers out of `excel_writer.py` and
  adds a new consumer of all of them.
- Deploying to PythonAnywhere — implementation-plan-level detail (pip install
  `reportlab` into both venvs, `git pull`, reload), not a design concern.
