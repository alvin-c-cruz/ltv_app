"""Verify a knock-out on the last day of the window reaches the printed page.

The "KO" marker goes in the O:X cell for the day *after* the breaching close.
When the knock-out lands on the last day of the 10-day window there is no such
cell, so no marker is written.

That day is the report date itself -- the likeliest day to find a freshly
discovered knock-out on a Friday report -- and it is the only chance the sheet
gets, because the contract drops out of every later report once it is flagged
`status='KO'`.

The Z:AJ tracking grid *does* mark it: on the final column the formula reads the
real breaching close and evaluates to "KO" for both an accumulator and a
decumulator. It simply was not printed -- `print_area` stopped at column X.

So the fix is to print it. Y (a dropped helper) and Z (the literal direction
flag, always 2) are hidden so they stay off the page, the same way C and M
already are, and AA:AJ are narrowed to suit their one-character contents.

    .venv/Scripts/python.exe scripts/verify_last_day_ko_marker.py
"""
import io
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import (
    _OX_COLS, _STATUS_COLS, _ko_offsets, _write_contracts, _write_status_grid,
    build_workbook)

SERVER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True


def check(label, actual, expected):
    global ok
    if actual == expected:
        print(f"  {label}: PASS")
    else:
        ok = False
        print(f"  {label}: FAIL  expected {expected!r}, got {actual!r}")


class _NeverHoliday:
    def is_holiday(self, d):
        return False


DATES = [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4),
         date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10),
         date(2026, 6, 11), date(2026, 6, 12)]
COUNT_ROW = 3
ROW = COUNT_ROW + 4


def _rec(**kw):
    base = dict(code_ref=1, stock_name='Test Stock NO GTD', stock_name_plain='Test Stock',
                code='0001', bank_doc='TEST-1', shares='100 / 200', spot=100.0,
                strike=80.0, ko=120.0, start_date=DATES[0], end_date=date(2027, 6, 1),
                received=1, total=12, yahoo_ticker='0001.HK', next_date=date(2026, 7, 1),
                frequency='monthly', ccy_id='HKD')
    base.update(kw)
    return base


KO_LAST_DAY = {**{d: 100.0 for d in DATES[:9]}, DATES[9]: 125.0}
KO_MIDWEEK = {DATES[0]: 100.0, DATES[1]: 110.0, DATES[2]: 125.0}


def build(rec, prices, product='ACCU'):
    wb = openpyxl.Workbook()
    ws = wb.active
    lookup = lambda c, d: prices.get(d)
    ko = _ko_offsets([rec], DATES, _NeverHoliday(), lookup)
    _write_contracts(ws, [rec], product, COUNT_ROW, DATES[-1], DATES, _NeverHoliday(),
                     price_lookup=lookup, bank_id='DBPe')
    _write_status_grid(ws, COUNT_ROW, 1, DATES, ko_offsets=ko)
    return ws, ko.get(0)


def isolated():
    print("Knock-out on the last day of the window (day 9 of 10):")
    ws, ko_idx = build(_rec(), KO_LAST_DAY)
    check("knock-out is on the final column", ko_idx, len(_OX_COLS) - 1)
    check("O:X has no room for the marker",
          any(ws[f'{c}{ROW}'].value == 'KO' for c in _OX_COLS), False)
    check("breaching close kept in X", ws[f'X{ROW}'].value, 125.0)
    check("final status cell AJ carries a formula over X",
          str(ws[f'AJ{ROW}'].value).startswith('=IF(ISTEXT(X'), True)

    print("\nKnock-out mid-window still marked in O:X (unchanged):")
    ws, _ = build(_rec(), KO_MIDWEEK)
    check("O:X carries the marker",
          any(ws[f'{c}{ROW}'].value == 'KO' for c in _OX_COLS), True)


def live_print_area():
    print("\nPrinted range on a generated workbook:")
    app = create_app()
    app.config["DATABASE"] = os.path.join(SERVER, "instance", "LTV Stocks.db")
    ctx = app.app_context()
    ctx.push()
    try:
        buf = build_workbook(get_db(), date(2026, 7, 10), ['DBPe'])
    finally:
        ctx.pop()

    wb = openpyxl.load_workbook(io.BytesIO(buf.getvalue()))
    sheets = [n for n in wb.sheetnames if wb[n].print_area]
    check("sheets with a print area", bool(sheets), True)

    # The printed range must not depend on whether anything knocked out --
    # every sheet ends at the same column, KO marker or no KO marker.
    last_cols = set()
    for name in sheets:
        ws = wb[name]
        area = ws.print_area[0] if isinstance(ws.print_area, list) else ws.print_area
        last_cols.add(area.split(':')[1].replace('$', '').rstrip('0123456789'))
    check("every sheet prints to the same last column", sorted(last_cols),
          [_STATUS_COLS[-1]])

    ws = wb[sheets[0]]
    check("helper column Y hidden", bool(ws.column_dimensions['Y'].hidden), True)
    check("direction-flag column Z hidden", bool(ws.column_dimensions['Z'].hidden), True)

    # Wide enough for "KO", no wider. The cells hold one or two characters.
    widths = {c: ws.column_dimensions[c].width for c in _STATUS_COLS}
    check("status columns all share one width", len(set(widths.values())), 1)
    w = next(iter(widths.values()))
    check("status column width fits 'KO' and stays narrow", 2.0 <= w <= 4.5, True)
    print(f"    (status column width = {w})")


def main():
    isolated()
    live_print_area()
    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
