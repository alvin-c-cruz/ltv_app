"""Verification for the /maris/ Transaction Range workbook's arrangement.

The sheet is grouped for reading rather than listed chronologically:

  account (bank priority) -> stock code -> trade date -> transaction type

with one blank, still-bordered row between stock groups. Currency is not a
sort term -- a stock belongs to exactly one currency, so ordering by code
already groups it.

Expectations are derived from the generated workbook and the database at
runtime; no figures are pasted in, so this is safe for the public repo.

    .venv/Scripts/python.exe scripts/verify_transaction_range_grouping.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

import openpyxl

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.marissa_orders.extensions import download_transaction_range

START, END = '2026-09-14', '2026-09-18'
failures = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def main():
    app = create_app()
    app.config['LOGIN_DISABLED'] = True
    with app.app_context():
        db = get_db()
        path = download_transaction_range(db, START, END)
        bank_pri = {r['bank_name']: r['priority']
                    for r in db.execute('SELECT bank_name, priority FROM tbl_bank_account')}
        type_pri = {r['transaction_type']: r['priority']
                    for r in db.execute('SELECT transaction_type, priority FROM tbl_transaction_type')}
        expected_n = db.execute(
            'SELECT COUNT(*) c FROM tbl_transaction WHERE trade_date >= ? AND trade_date <= ?',
            (START, END)).fetchone()['c']

    ws = openpyxl.load_workbook(path).active

    data, blanks = [], []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        vals = [c.value for c in row[:7]]
        if all(v is None for v in vals):
            blanks.append(row)
            continue
        data.append({'date': str(vals[0])[:10], 'bank': vals[1],
                     'type': vals[2], 'code': vals[3], 'row': row})

    check(len(data) == expected_n,
          'every transaction in the range appears (%d of %d)' % (len(data), expected_n))

    # Sort key, in file order.
    keys = [(bank_pri.get(d['bank']), d['code'], d['date'], type_pri.get(d['type']))
            for d in data]
    check(keys == sorted(keys), 'rows follow account -> stock -> date -> type priority')

    # A blank row between every stock-group change, and nowhere else.
    groups = []
    for d in data:
        g = (d['bank'], d['code'])
        if not groups or groups[-1] != g:
            groups.append(g)
    check(len(blanks) == max(0, len(groups) - 1),
          'one blank row per stock-group boundary (%d blanks, %d groups)'
          % (len(blanks), len(groups)))

    # Blanks keep the border -- an unbordered gap breaks the grid.
    bordered = all(c.border.top.style and c.border.bottom.style
                   for row in blanks for c in row[:7])
    check(not blanks or bordered, 'blank separator rows keep their borders')

    # No blank leads or trails the data.
    first = data and data[0]['row'][0].row == 2
    check(first, 'the first data row sits directly under the header')

    print('\nRESULT: %s' % ('ALL PASS' if not failures else 'FAIL (%d)' % len(failures)))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
