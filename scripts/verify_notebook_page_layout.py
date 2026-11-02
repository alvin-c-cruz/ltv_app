"""Regression harness: notebook account blocks are laid out on 5.5 x 8.5 pages the
way Alvin lays them out by hand.

His October notebooks put an account heading on the first row of every page the
account lines reach -- rows 42, 74, 106, 138: page 1 ends on row 41 (rows 5-23
are the 12 pt card) and each later page holds 32 rows under the title rows 1:2.
A numbered line item is never split across a page; when the next one does not
fit, the rest of the page stays blank and the next page opens with the account's
heading again, the numbering carrying on. A stock's balance lines stay with its
last trade. He chose to have the app do this on 2026-10-27 (BUGS.md 2026-10-26,
item 2).

For each of the newest trade dates with a notebook, generated through the route:
  L1  every page start inside the account lines holds an account heading;
  L2  no line item (numbered title through its last line) crosses a page end;
  L3  a stock's balance lines end on the page its last trade starts on;
  L4  within an account the items run 1, 2, 3 ... across repeated headings, and a
      new account starts again at 1;
  L5  no transfer (its nine lines, title to Average) crosses a page end -- on
      20 Oct he moved the whole Transfer of Stocks section to a new page for it;
  L6  the sheet is set to paper 10000, the "Notebook" form (5.5 x 8.5 in) the page model assumes;
Plus R1-R5, place_heading() on fixed sizes shaped like his October pages (the
sampled dates may not happen to exercise every rule).
Both a repeated (continuation) heading and an account opening a page are required
somewhere in the sample, so the rules cannot pass by never coming up. No figure
is printed.

Run: server/.venv/Scripts/python.exe scripts/verify_notebook_page_layout.py
"""
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from openpyxl import load_workbook

from ltv_app import create_app

DB_PATH = os.path.join(SERVER, "instance", "LTV Stocks.db")
FIRST_PAGE_END = 41
PAGE_ROWS = 32
FIRST_ACCOUNT_ROW = 24
DATES_TO_CHECK = 40

app = create_app({"DATABASE": DB_PATH, "LOGIN_DISABLED": True})
client = app.test_client()
ok = True


def _case(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL")


def _page_end(row):
    if row <= FIRST_PAGE_END:
        return FIRST_PAGE_END
    return FIRST_PAGE_END + PAGE_ROWS * math.ceil((row - FIRST_PAGE_END) / PAGE_ROWS)


def _notebook(trade_date):
    r = client.get(f"/notebook/generate/{trade_date}")
    data = r.get_data()
    r.close()
    return load_workbook(io.BytesIO(data))["notebook"] if r.status_code == 200 else None


def _layout(ws):
    """Account headings {row: text}, numbered items [(title row, last row, number)],
    balance 'remaining' rows, and the last row of the account section."""
    headings = {rng.min_row: ws.cell(rng.min_row, 1).value for rng in ws.merged_cells.ranges
                if rng.min_col == 1 and rng.max_col == 17 and rng.min_row >= FIRST_ACCOUNT_ROW
                and ws.cell(rng.min_row, 1).value}
    transfers = next((r for r in range(FIRST_ACCOUNT_ROW, ws.max_row + 1)
                      if ws.cell(r, 3).value == "Transfer of Stocks"), ws.max_row + 1)
    items, remaining, last = [], [], FIRST_ACCOUNT_ROW
    for r in range(FIRST_ACCOUNT_ROW, transfers):
        if any(ws.cell(r, c).value is not None for c in range(1, 18)):
            last = r
        number = ws.cell(r, 2).value
        if isinstance(number, int) and ws.cell(r, 3).value:
            end = r
            while ws.cell(end + 1, 3).value is not None and not isinstance(ws.cell(end + 1, 2).value, int) \
                    and end + 1 not in headings:
                end += 1
            items.append((r, end, number))
        f = ws.cell(r, 6).value
        if isinstance(f, str) and f.startswith('=IF(G') and '"shares","short"' in f:
            remaining.append(r)
    return headings, items, remaining, min(last, transfers - 1)


with app.app_context():
    from ltv_app.blueprints.database.views import get_db
    dates = [r[0] for r in get_db().execute(
        "SELECT DISTINCT substr(trade_date, 1, 10) FROM tbl_transaction ORDER BY 1 DESC").fetchall()]

TRANSFER_ROWS = 9

seen = {"continuation heading": 0, "page-opening account": 0, "transfer": 0}
wrong = {"L1": 0, "L2": 0, "L3": 0, "L4": 0, "L5": 0, "L6": 0}
checked = 0
for trade_date in dates:
    if checked >= DATES_TO_CHECK:
        break
    ws = _notebook(trade_date)
    if ws is None:
        continue
    checked += 1
    if ws.page_setup.paperSize != 10000:
        wrong["L6"] += 1
    headings, items, remaining, section_end = _layout(ws)

    page_start = FIRST_PAGE_END + 1
    while page_start <= section_end:
        if page_start not in headings:
            wrong["L1"] += 1
        page_start += PAGE_ROWS

    for title, end, _ in items:
        if _page_end(title) < end:
            wrong["L2"] += 1

    for r in remaining:
        last_title = max((t for t, _, _ in items if t < r), default=None)
        if last_title is not None and _page_end(last_title) < r:
            wrong["L3"] += 1

    order = sorted(list(headings.items()) + [(t, n) for t, _, n in items])
    current, expected = None, None
    for row, value in order:
        if row in headings:
            at_page_start = row > FIRST_PAGE_END and (row - FIRST_PAGE_END - 1) % PAGE_ROWS == 0
            if value != current:
                current, expected = value, 1
                if at_page_start:
                    seen["page-opening account"] += 1
            elif at_page_start:
                seen["continuation heading"] += 1
        else:
            if value != expected:
                wrong["L4"] += 1
                expected = value
            expected += 1

    for r in range(section_end + 1, ws.max_row + 1):
        title = ws.cell(r, 3).value
        if isinstance(ws.cell(r, 2).value, int) and isinstance(title, str) and title.startswith("Transfer ") \
                and title != "Transfer of Stocks":
            seen["transfer"] += 1
            if _page_end(r) < r + TRANSFER_ROWS - 1:
                wrong["L5"] += 1

_case(f"L0 notebooks generated ({checked})", checked >= 10, True)
for shape, count in seen.items():
    _case(f"   a {shape} exists to test", count > 0, True)
_case("L1 page starts inside the account lines without an account heading", wrong["L1"], 0)
_case("L2 line items crossing a page end", wrong["L2"], 0)
_case("L3 balance lines ending on a later page than their last trade", wrong["L3"], 0)
_case("L4 items out of sequence within an account", wrong["L4"], 0)
_case("L5 transfers crossing a page end", wrong["L5"], 0)
_case("L6 notebooks not on the Notebook form (paper 10000)", wrong["L6"], 0)

# place_heading(row it would take after two blank rows, last row written above, unit sizes)
from ltv_app.blueprints.notebook.extensions.create_notebook import page_end, place_heading

TRANSFER = (9, 10)
_case("R0 pages end on rows 41, 73, 105", [page_end(41), page_end(42), page_end(74)], [41, 73, 105])
_case("R1 a gap reaching a page start puts the heading on it",
      place_heading(44, 41, [(3, 4)]), 42)
_case("R2 a section whose first unit would cross the page end starts on the next page",
      place_heading(130, 127, [TRANSFER] * 3), 138)
_case("R3 one blank row instead of two when that keeps more on the page",
      place_heading(33, 30, [(2, 3), (6, 8), (6, 7)]), 32)
_case("R4 two blank rows when one would not keep more on the page",
      place_heading(33, 30, [(2, 3), (3, 4)]), 33)
_case("R5 a section whose first unit fits starts where it falls",
      place_heading(61, 58, [(3, 4), (20, 21)]), 61)

print("RESULT:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
