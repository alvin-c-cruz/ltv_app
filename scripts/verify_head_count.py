"""Verify the ACCU/DECU table head count in the LTV Stocks workbook.

The head count in column A of a contract block is an Excel formula:

    ={n}-COUNTIF(N<first>:N<last>,"*DONE*")[-{k}]

`n` is the number of contracts in the block, the COUNTIF drops the ones that
have finished delivering (`received == total`, written as DONE in column N),
and `k` drops the ones that knocked out inside the report window.

A contract can be both. It carries DONE in column N *and* appears in
`_ko_offsets`, so counting it in `k` as well subtracts it twice and the cell
can render a negative head count -- which also propagates into the cross-sheet
totals, because `hkd_count[bank_id][product]` points at this cell.

Runs entirely on synthetic records: no database, no client figures.

    .venv/Scripts/python.exe scripts/verify_head_count.py
"""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import _write_contracts

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


# A 10-day window shaped like week_dates(): prev Mon-Fri + current Mon-Fri.
DATES = [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4),
         date(2026, 6, 5), date(2026, 6, 8), date(2026, 6, 9), date(2026, 6, 10),
         date(2026, 6, 11), date(2026, 6, 12)]
REPORT_DATE = DATES[-1]
COUNT_ROW = 3


def _rec(**kw):
    base = dict(code_ref=1, stock_name='Test Stock NO GTD', stock_name_plain='Test Stock',
                code='0001', bank_doc='TEST-1', shares='100 / 200', spot=100.0,
                strike=80.0, ko=120.0, start_date=DATES[0], end_date=date(2027, 6, 1),
                received=1, total=12, yahoo_ticker='0001.HK', next_date=date(2026, 7, 1),
                frequency='monthly', ccy_id='HKD')
    base.update(kw)
    return base


# An accumulator (spot > strike) knocks out when the close reaches ko=120.
KNOCKS_OUT = {DATES[0]: 100.0, DATES[1]: 110.0, DATES[2]: 125.0}
NEVER_KNOCKS = {d: 100.0 for d in DATES}


def head_count(records, prices):
    wb = openpyxl.Workbook()
    ws = wb.active
    _write_contracts(ws, records, 'ACCU', COUNT_ROW, REPORT_DATE, DATES,
                     _NeverHoliday(), price_lookup=lambda c, d: prices.get(d),
                     bank_id='DBPe')
    return ws[f'A{COUNT_ROW}'].value


def expected(n, subtract):
    first = COUNT_ROW + 4
    f = f'={n}-COUNTIF(N{first}:N{first + n - 1},"*DONE*")'
    return f + (f'-{subtract}' if subtract else '')


def main():
    print("Head count formula checks:")

    # Live contract, no knock-out: nothing to subtract beyond the COUNTIF.
    check("live contract, no KO",
          head_count([_rec(received=1, total=12)], NEVER_KNOCKS),
          expected(1, 0))

    # Knocked out and still delivering: subtracted once, by the -k term.
    check("KO, not DONE",
          head_count([_rec(received=1, total=12)], KNOCKS_OUT),
          expected(1, 1))

    # Finished delivering, no knock-out: subtracted once, by the COUNTIF.
    check("DONE, no KO",
          head_count([_rec(received=12, total=12)], NEVER_KNOCKS),
          expected(1, 0))

    # Both. The COUNTIF already removes it, so -k must not remove it again --
    # otherwise this single-contract block reports a head count of -1.
    check("DONE and KO -- counted once, not twice",
          head_count([_rec(received=12, total=12)], KNOCKS_OUT),
          expected(1, 0))

    # Mixed block: both rows knock out, only the live one is left to subtract.
    check("one DONE+KO, one KO-not-DONE",
          head_count([_rec(received=12, total=12), _rec(received=1, total=12)], KNOCKS_OUT),
          expected(2, 1))

    print("\nPASS" if ok else "\nFAIL")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
