"""Active-count / KO handling for the LTV Stocks report."""
import sqlite3

from ltv_app.blueprints.ltv_stocks.create_ltv_stocks import _load_contracts


def _add_contract(conn, ref_num, ttype, status):
    conn.execute(
        "INSERT INTO tbl_stock_contract "
        "(ref_num, reference, bank_ref, code_ref, trade_date, start_date, "
        " transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) "
        "VALUES (?, ?, 1, 1, '2026-01-01', '2026-01-01', ?, 1000, 'No', "
        " 100.0, 95.0, 110.0, '12m', 'monthly', '1m', 'DOC', ?)",
        (ref_num, f"REF{ref_num}", ttype, status),
    )
    # One unreceived period so the contract is not DONE (remaining > 0).
    conn.execute(
        "INSERT INTO tbl_stock_contract_period "
        "(contract_ref, start_date, end_date, days, received, gtd) "
        "VALUES (?, '2026-01-01', '2026-01-31', '20', '', '1m')",
        (ref_num,),
    )


def test_load_contracts_sets_is_ko(app):
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    _add_contract(conn, 10, 'ACCU', 'active')
    _add_contract(conn, 11, 'ACCU', 'KO')
    conn.commit()

    result = {}
    _load_contracts(conn, result, {})
    conn.close()

    accu = result['HKD']['CB1']['accu']
    by_ref = {c['ref_num']: c for c in accu}

    assert by_ref[10]['is_ko'] is False
    assert by_ref[11]['is_ko'] is True
    # KO contract is not DONE and keeps a date in the next-month column.
    assert by_ref[11]['is_done'] is False
    assert by_ref[11]['next_date'] != 'DONE'


from openpyxl import load_workbook

from ltv_app.blueprints.ltv_stocks.views import _active_count, _generate_excel
from datetime import date


def test_active_count_excludes_done_and_ko():
    contracts = [
        {'is_done': False, 'is_ko': False},  # active   -> counted
        {'is_done': True,  'is_ko': False},  # done     -> excluded
        {'is_done': False, 'is_ko': True},   # ko       -> excluded
        {'is_done': False, 'is_ko': False},  # active   -> counted
    ]
    assert _active_count(contracts) == 2
    assert _active_count([]) == 0


def _contract(**overrides):
    base = {
        'stock_name': 'Tencent', 'code': '700', 'code_ref': 1, 'bank_doc': 'DOC',
        'shares_day': '1,000', 'spot_raw': 100.0, 'strike_raw': 95.0, 'ko_raw': 110.0,
        'start_date_raw': date(2026, 1, 1), 'last_end_date_raw': date(2026, 1, 31),
        'received_months': 1.0, 'remaining_months': 11.0, 'total_months': 12,
        'next_date': '2026-08-01', 'is_done': False, 'is_ko': False,
    }
    base.update(overrides)
    return base


def test_generate_excel_count_is_plain_integer():
    accu = [
        _contract(),                    # active
        _contract(is_ko=True),          # ko
        _contract(is_done=True, next_date='DONE'),  # done
    ]
    data = {'HKD': {'CB1': {
        'bank_name': 'Citibank No. 1', 'bank_priority': 1, 'report_label': None,
        'accu': accu, 'decu': [], 'positions': {},
    }}}

    output = _generate_excel(data, date(2026, 7, 2), {}, [])
    wb = load_workbook(output)
    ws = wb['CB1-HKD']

    # ACCU count cell is column A of the section's first row (A3).
    value = ws['A3'].value
    assert value == 1
    assert isinstance(value, int)
    assert not (isinstance(value, str) and str(value).startswith('='))
