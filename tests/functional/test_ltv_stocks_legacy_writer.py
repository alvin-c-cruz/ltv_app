from datetime import date

import openpyxl

from ltv_app.blueprints.ltv_stocks.legacy_port.excel_writer import (
    _write_contracts,
    week_dates,
)


class _FakeWorkingDay:
    """Weekend-only holiday check; no DB access needed for this unit test."""

    def is_holiday(self, d):
        return d.weekday() >= 5


def _record(ref_num, code, code_ref, *, received, total, next_date,
            start_date, end_date, ccy_id='HKD'):
    return {
        'ref_num': ref_num,
        'reference': f'REF{ref_num}',
        'bank_doc': f'DOC{ref_num}',
        'frequency': 'monthly',
        'stock_name': f'Stock {code} GTD 1m',
        'code': code,
        'code_ref': code_ref,
        'yahoo_ticker': f'{code}.HK',
        'shares': '1,000',
        'spot': 100.0,
        'strike': 95.0,
        'ko': 110.0,
        'start_date': start_date,
        'end_date': end_date,
        'total': total,
        'received': received,
        'next_date': next_date,
        'remaining': total - received,
        'ccy_id': ccy_id,
        'daily_shares': 1000,
        'leveraged': 'No',
        'indicative': 'YES',
        'status': 'active',
    }


def test_write_contracts_headers_and_data_rows():
    report_date = date(2026, 7, 6)
    date_range = week_dates(report_date)

    active = _record(
        1, '0700', 700, received=1.0, total=3.0,
        next_date=date(2026, 8, 1),
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
    )
    done = _record(
        2, '9988', 9988, received=3.0, total=3.0,
        next_date=None,
        start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
    )
    records = [active, done]

    wb = openpyxl.Workbook()
    ws = wb.active

    next_row = _write_contracts(
        ws, records, 'ACCU', 1, report_date, date_range,
        _FakeWorkingDay(), price_lookup=lambda code_ref, d: None,
    )

    values = {cell.value for row in ws.iter_rows() for cell in row}
    assert 'ACCUMULATOR' in values
    assert 'RCVD mos.' in values
    assert 'NEXT MO.' in values

    first_data_row = 1 + 4
    active_row = first_data_row
    done_row = first_data_row + 1

    assert ws[f'K{active_row}'].value == f'=L{active_row}-J{active_row}'
    assert ws[f'K{done_row}'].value == f'=L{done_row}-J{done_row}'

    assert ws[f'N{done_row}'].value == 'DONE'
    assert isinstance(ws[f'N{active_row}'].value, date)

    assert ws['A1'].value == f'=2-COUNTIF(N{first_data_row}:N{done_row},"*DONE*")'

    assert ws.column_dimensions['C'].hidden is True
    assert ws.column_dimensions['M'].hidden is True

    assert next_row == done_row + 1 + 2


def test_week_dates_uses_isoweekday_and_has_ten_dates():
    report_date = date(2026, 7, 6)  # Monday
    dates = week_dates(report_date)
    assert len(dates) == 10
    # Monday isoweekday() == 1 -> start = report_date - timedelta(days=7)
    assert dates[0] == date(2026, 6, 29)
    assert dates == [
        date(2026, 6, 29), date(2026, 6, 30), date(2026, 7, 1),
        date(2026, 7, 2), date(2026, 7, 3),
        date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 8),
        date(2026, 7, 9), date(2026, 7, 10),
    ]
