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
