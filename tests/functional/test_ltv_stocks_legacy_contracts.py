import sqlite3
from datetime import date
from ltv_app.blueprints.ltv_stocks.legacy_port.term_sheet_calc import contract_records


def _contract(conn, ref, ttype, *, frequency='monthly', gtd='1m', leveraged='No',
              daily=1000, spot=100.0, strike_rate=95.0, ko_rate=110.0, status='active',
              start='2026-01-01'):
    conn.execute(
        "INSERT INTO tbl_stock_contract (ref_num, reference, bank_ref, code_ref, trade_date, "
        " start_date, transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) VALUES (?,?,1,1,?,?,?,?,?,?,?,?, '12m',?,?, 'DOC',?)",
        (ref, f'REF{ref}', start, start, ttype, daily, leveraged, spot, strike_rate, ko_rate,
         frequency, gtd, status))


def _period(conn, ref, end_date, received, days='20'):
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (?, '2026-01-01', ?, ?, ?, '1m')", (ref, end_date, days, received))


def test_received_breaks_on_first_empty(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 10, 'ACCU', frequency='monthly')
    _period(conn, 10, '2026-01-31', '1000')   # filled
    _period(conn, 10, '2026-02-28', '1000')   # filled
    _period(conn, 10, '2026-03-31', '')       # EMPTY -> break here
    _period(conn, 10, '2026-04-30', '1000')   # filled but AFTER the gap -> not counted
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[10]
    conn.close()
    assert rec['total'] == 4          # monthly: 4 period rows
    assert rec['received'] == 2       # consecutive filled before first empty
    assert rec['remaining'] == 2
    assert rec['next_date'] is not None   # next working day after 2026-03-31


def test_total_divides_by_frequency(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 11, 'ACCU', frequency='bi-monthly')
    _period(conn, 11, '2026-01-15', '1000'); _period(conn, 11, '2026-01-31', '1000')
    _period(conn, 11, '2026-02-15', '')
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[11]
    conn.close()
    assert rec['total'] == 1.5        # 3 periods / 2
    assert rec['received'] == 1.0     # 2 filled * 0.5


def test_all_filled_is_done(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 12, 'ACCU', frequency='monthly')
    _period(conn, 12, '2026-01-31', '1000')
    conn.commit()
    rec = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}[12]
    conn.close()
    assert rec['received'] == rec['total'] == 1
    assert rec['next_date'] is None    # never hit an empty period


def test_gtd_suffix(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 13, 'ACCU', gtd='No');  _period(conn, 13, '2026-01-31', '')
    _contract(conn, 14, 'ACCU', gtd='Yes'); _period(conn, 14, '2026-01-31', '')
    _contract(conn, 15, 'ACCU', gtd='3m');  _period(conn, 15, '2026-01-31', '')
    conn.commit()
    recs = {r['ref_num']: r for r in contract_records(conn, 1, 'ACCU')}
    conn.close()
    assert recs[13]['stock_name'].endswith('NO GTD')
    assert recs[14]['stock_name'].endswith('GTD 1m')
    assert recs[15]['stock_name'].endswith('GTD 3m')


def test_no_periods_skipped(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _contract(conn, 16, 'ACCU'); conn.commit()   # no periods
    recs = {r['ref_num'] for r in contract_records(conn, 1, 'ACCU')}
    conn.close()
    assert 16 not in recs
