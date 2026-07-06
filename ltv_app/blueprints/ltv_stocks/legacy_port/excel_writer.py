"""Excel writer — contract tables.

Ports the contract-table portion of `localhost/modules/ltv_stocks2.py`'s
`contract()` method (lines 410-709) cell-for-cell, dropping the AA-AJ
per-day status columns and the off-print-area helper columns `Z` (leverage
flag) and `AK` (reference) — see docs/superpowers/specs/
2026-07-06-ltv-stocks-legacy-exact-replica-design.md, "The Excel writer".

`week_dates`, the style-constant factories, and `_write_contracts` are the
public surface consumed by Phase 5 (`build_workbook`/`report_header`/
`_write_positions`, not implemented here).
"""

from datetime import date, timedelta

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.styles.borders import Border, Side
from openpyxl.styles.fills import PatternFill

from .term_sheet_calc import _FREQ_DIV


# --- Style constants (port of ltv_stocks2's xl_font/xl_fill/xl_box/xl_align lambdas) ---

def xl_font(size=10, bold=False, name='Arial'):
    return Font(name=name, size=size, bold=bold)


def xl_font_color(size=10, color='00000000', bold=True, name='Arial'):
    return Font(name=name, size=size, bold=bold, color=color)


def xl_align(wrap_text=False, horizontal='center', vertical='center'):
    return Alignment(horizontal=horizontal, vertical=vertical, wrap_text=wrap_text)


def xl_align_shrink(shrink_to_fit=True, vertical='center'):
    return Alignment(vertical=vertical, shrink_to_fit=shrink_to_fit)


def xl_box():
    side = Side(style='thin')
    return Border(left=side, right=side, top=side, bottom=side)


def xl_fill(fill_color):
    return PatternFill(patternType='solid', fgColor=fill_color)


# Per-code background fills for column A (ltv_stocks2.py ~688-704).
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

_GREY_FILL = '00C0C0C0'

# O-X column -> offset into the 10-date range.
_COL_DATE_OFFSET = {
    'O': 0, 'P': 1, 'Q': 2, 'R': 3, 'S': 4,
    'T': 5, 'U': 6, 'V': 7, 'W': 8, 'X': 9,
}
_OX_COLS = ('O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')
_ALL_DATA_COLS = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N') + _OX_COLS
_ZERO_ROW_COLS = ('A', 'B', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X')


def week_dates(report_date: date) -> list:
    """The 10-date range: previous Mon-Fri + current Mon-Fri, built with isoweekday()."""
    start = report_date - timedelta(days=6 + report_date.isoweekday())
    offsets = (0, 1, 2, 3, 4, 7, 8, 9, 10, 11)
    return [start + timedelta(days=o) for o in offsets]


def _write_contracts(ws, records, product, row, report_date, date_range, wd, price_lookup):
    """Write one ACCU/DECU contract table starting at `row`. Returns the next free row.

    `wd` supplies `.is_holiday(date) -> bool` for the O-X grid (a `WorkingDay`
    instance scoped to the table's currency). `price_lookup(code_ref, date) ->
    float|None` supplies the O-X historical closing prices.
    """
    ws.column_dimensions['C'].hidden = True
    ws.column_dimensions['M'].hidden = True

    n = len(records)
    count_row = row
    first_data_row = count_row + 4
    last_data_row = first_data_row + n - 1

    # Head Count
    cell = ws[f'A{count_row}']
    cell.value = f'={n}-COUNTIF(N{first_data_row}:N{last_data_row},"*DONE*")'
    cell.font = xl_font(7)
    cell.number_format = '0'
    cell.alignment = xl_align(False, 'left')
    ws.row_dimensions[count_row].height = 10.5

    row = count_row + 1

    # Head Line 1
    labels = {
        'A': f'{product}MULATOR',
        'B': 'CODE',
        'C': 'Bank Reference',
        'D': 'SHARES / DAY',
        'E': 'SPOT PRICE',
        'F': 'STRIKE PRICE',
        'G': 'K/O PRICE',
        'H': 'START DATE',
        'I': 'END DATE',
        'J': 'LIFE TERM OF CONTRACT',
        'N': f'DATE OF {product}MULATOR',
        'O': 'CLOSING PRICE',
        'T': 'CLOSING PRICE',
    }
    for col, val in labels.items():
        cell = ws[f'{col}{row}']
        cell.value = val
        cell.font = xl_font(6, True) if col in ('J', 'N') else xl_font(8, True)
        cell.alignment = xl_align(True) if col in ('E', 'F', 'G', 'J', 'N') else xl_align()
        cell.border = xl_box()

    for col in ('B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'):
        ws.merge_cells(f'{col}{row}:{col}{row + 2}')
    ws.merge_cells(f'J{row}:L{row}')
    ws.merge_cells(f'N{row}:N{row + 1}')
    ws.merge_cells(f'O{row}:S{row}')
    ws.merge_cells(f'T{row}:X{row}')

    row += 1

    # Head Line 2
    labels = {
        'A': ('Strike Price < Closing Price = QTYx1' if product == 'ACCU'
              else 'Strike Price > Closing Price = QTYx1'),
        'J': 'RCVD mos.',
        'K': 'REM mos.',
        'L': 'Total mos.',
    }
    for col, offset in _COL_DATE_OFFSET.items():
        labels[col] = date_range[offset]

    for col, val in labels.items():
        cell = ws[f'{col}{row}']
        cell.value = val
        cell.font = xl_font(7, True)
        cell.alignment = xl_align(True)
        cell.border = xl_box()
        if col in _OX_COLS:
            cell.font = xl_font(9, True)
            cell.number_format = 'm/d'

    for col in ('J', 'K', 'L') + _OX_COLS:
        ws.merge_cells(f'{col}{row}:{col}{row + 1}')

    row += 1

    # Head Line 3
    labels = {
        'A': ('Strike Price > Closing Price = QTYx2' if product == 'ACCU'
              else 'Strike Price < Closing Price = QTYx2'),
        'N': 'NEXT MO.',
    }
    for col, val in labels.items():
        cell = ws[f'{col}{row}']
        cell.value = val
        cell.font = xl_font(7, True)
        cell.alignment = xl_align(True)
        cell.border = xl_box()

    row += 1  # == first_data_row

    if n == 0:
        for col in _ZERO_ROW_COLS:
            ws[f'{col}{row}'].border = xl_box()
        ws.row_dimensions[row].height = 17
    else:
        for rec in records:
            r = row
            done = False
            divisor = _FREQ_DIV.get(rec.get('frequency'), 2)

            cols = {
                'A': rec['stock_name'],
                'B': rec['code'],
                'C': rec['bank_doc'],
                'D': rec['shares'],
                'E': rec['spot'],
                'F': rec['strike'],
                'G': rec['ko'],
                'H': rec['start_date'],
                'I': rec['end_date'],
                'J': rec['received'],
                'K': f'=L{r}-J{r}',
                'L': rec['total'],
                'M': rec['yahoo_ticker'],
                'N': rec['next_date'],
            }
            for col, offset in _COL_DATE_OFFSET.items():
                cols[col] = price_lookup(rec['code_ref'], date_range[offset])

            ws.row_dimensions[r].height = 17 if rec.get('ccy_id') == 'HKD' else 25.5

            for col in _ALL_DATA_COLS:
                cell = ws[f'{col}{r}']
                cell.font = xl_font(10) if col != 'F' else xl_font(10, True)
                cell.alignment = xl_align(False) if col != 'A' else xl_align(False, 'left')

                if col in ('E', 'F', 'G'):
                    cell.number_format = '#,##0.0000'
                elif col in ('J', 'K', 'L'):
                    cell.number_format = '0' if divisor == 1 else '0.0'
                elif col == 'B':
                    cell.number_format = '@'
                elif col in ('H', 'I', 'N'):
                    cell.font = xl_font(9)
                    cell.number_format = 'd-mmm-yy'
                elif col in _OX_COLS:
                    cell.number_format = '#,##0.00'
                cell.border = xl_box()

                if col == 'N':
                    if rec['received'] != rec['total']:
                        cell.value = cols[col]
                    else:
                        cell.value = 'DONE'
                        cell.font = xl_font(10, True)
                elif col in _OX_COLS:
                    d = date_range[_COL_DATE_OFFSET[col]]
                    if d < rec['start_date']:
                        cell.fill = xl_fill(_GREY_FILL)
                    elif d > rec['end_date']:
                        k = _COL_DATE_OFFSET[col]
                        if k == 4:
                            if d == rec['end_date'] + timedelta(days=3):
                                cell.value = 'Done'
                                done = True
                                cell.font = xl_font(10, True)
                            elif wd.is_holiday(d):
                                if done:
                                    cell.fill = xl_fill(_GREY_FILL)
                                else:
                                    cell.value = 'Done'
                                    done = True
                                    cell.font = xl_font(10, True)
                            else:
                                cell.fill = xl_fill(_GREY_FILL)
                        elif k > 4:
                            if d == rec['end_date'] + timedelta(days=1):
                                cell.value = 'Done'
                                done = True
                                cell.font = xl_font(10, True)
                            elif wd.is_holiday(d):
                                if done:
                                    cell.fill = xl_fill(_GREY_FILL)
                                else:
                                    cell.value = 'Done'
                                    done = True
                                    cell.font = xl_font(10, True)
                            else:
                                cell.fill = xl_fill(_GREY_FILL)
                        else:
                            cell.fill = xl_fill(_GREY_FILL)
                    elif wd.is_holiday(d):
                        cell.fill = xl_fill(_GREY_FILL)
                    else:
                        if d == report_date:
                            if rec['ccy_id'] != 'USD':
                                cell.value = (
                                    f'=INDEX(closing_price!A:C,MATCH(M{r},'
                                    f'closing_price!A:A,),3)'
                                )
                            else:
                                cell.value = None
                        elif cols[col]:
                            cell.value = cols[col]
                        else:
                            cell.value = None
                else:
                    cell.value = cols[col]

            cell_a = ws[f'A{r}']
            fill_color = _CODE_FILLS.get(rec['code'])
            if fill_color:
                cell_a.fill = xl_fill(fill_color)
            elif rec['code'] in _SMALL_FONT_CODES:
                cell_a.font = xl_font(9)

            row += 1

    return row + 2
