import sqlite3
from datetime import date

from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import position_records


BANK_REF = 1       # seeded 'CB1', indicative=NULL, transaction_basis='value_date'
BANK_ID = 'CB1'
CCY_ID = 'HKD'
CODE_REF = 1       # seeded '700'


def _txn(conn, ref, bank_ref, code_ref, trade_date, quantity, price=100.0, ttype='Buy (Spot)'):
    conn.execute(
        "INSERT INTO tbl_transaction "
        "(ref_num, trade_date, value_date, bank_ref, code_ref, transaction_type, quantity, price, "
        " brokerage, commission, foreign_charge, stamp_duty, misc) "
        "VALUES (?,?,?,?,?,?,?,?,0,0,0,0,0)",
        (ref, trade_date, trade_date, bank_ref, code_ref, ttype, quantity, price)
    )


def _contract(conn, ref, ttype, bank_ref=BANK_REF, code_ref=CODE_REF, *, leveraged='No',
              daily=1000, spot=100.0, strike_rate=95.0, ko_rate=110.0, status='active',
              start='2026-01-01'):
    conn.execute(
        "INSERT INTO tbl_stock_contract (ref_num, reference, bank_ref, code_ref, trade_date, "
        " start_date, transaction_type, daily_shares, leveraged, spot, strike_rate, ko_rate, "
        " tenor, frequency, gtd, bank_doc, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, '12m','monthly','1m', 'DOC',?)",
        (ref, f'REF{ref}', bank_ref, code_ref, start, start, ttype, daily, leveraged, spot,
         strike_rate, ko_rate, status))


def _period(conn, ref, end_date, received='', days='20'):
    conn.execute("INSERT INTO tbl_stock_contract_period "
                 "(contract_ref, start_date, end_date, days, received, gtd) "
                 "VALUES (?, '2026-01-01', ?, ?, ?, '1m')", (ref, end_date, days, received))


def test_blocked_equals_future_period_total_shares(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)   # big balance so no cap
    _contract(conn, 100, 'DECU', daily=1000)
    _period(conn, 100, '2026-07-31')   # end_date well after report_date -> blocks
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    assert '700' in recs
    rec = recs['700']
    assert rec['balance'] == 50000
    assert rec['blocked'] == 20 * 1000       # days * daily_shares, leveraged='No'
    assert rec['unblocked'] == 50000 - 20000


def test_past_period_does_not_block(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)
    _contract(conn, 101, 'DECU', daily=1000)
    _period(conn, 101, '2026-01-31')   # end_date well BEFORE cutoff -> does not block
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    rec = recs['700']
    assert rec['blocked'] == 0
    assert rec['unblocked'] == 50000


def test_blocked_capped_at_balance(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 100)   # small balance
    _contract(conn, 102, 'DECU', daily=1000)
    _period(conn, 102, '2026-07-31')   # total_shares = 20*1000 = 20000 >> balance
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    rec = recs['700']
    assert rec['balance'] == 100
    assert rec['blocked'] == 100
    assert rec['unblocked'] == 0


def test_accu_contract_does_not_block(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)
    _contract(conn, 103, 'ACCU', daily=1000)
    _period(conn, 103, '2026-07-31')
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    rec = recs['700']
    assert rec['blocked'] == 0
    assert rec['unblocked'] == 50000


def test_positions_sorted_by_code(app):
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO tbl_code VALUES (2,'005',NULL,'HSBC Holdings',NULL,NULL,1)"
    )
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 1000)   # code '700'
    _txn(conn, 2, BANK_REF, 2, '2026-01-01', 500)           # code '005'
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    assert list(recs.keys()) == ['005', '700']


def test_indicative_bank_uses_start_date_not_report_date_as_cutoff(app):
    """Port of ltv_stocks2.py's Gather_Info (line 33): the balance/blocked-shares
    snapshot is taken as of `start_date` -- the HKD-working-day walk-back to the
    current week's Monday -- not `report_date` itself. For report_date
    2026-07-06 (a Monday), start_date walks back a full week to 2026-06-29.
    For an indicative bank, `blocked_shares`' cutoff is exactly `start_date`
    (ltv_stocks2.py's `blocked_shares.__init__`: `check_end_date = observation_date`
    where `observation_date` is `start_date`, not the previous working day)."""
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    conn.execute("UPDATE tbl_bank_account SET indicative = 'YES' WHERE ref_num = ?", (BANK_REF,))
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)
    _contract(conn, 104, 'DECU', daily=1000)
    # end_date == start_date (2026-06-29) itself: for an indicative bank the
    # cutoff is start_date, so end_date > cutoff is False -> should NOT block.
    _period(conn, 104, '2026-06-29')
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    rec = recs['700']
    assert rec['blocked'] == 0
    assert rec['unblocked'] == 50000


def test_non_indicative_bank_uses_previous_day_of_start_date_as_cutoff(app):
    """Same end_date (start_date itself) but a non-indicative bank: cutoff is the
    working day *before* start_date, so end_date > cutoff -> blocks."""
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)
    _contract(conn, 105, 'DECU', daily=1000)
    _period(conn, 105, '2026-06-29')
    conn.commit()

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    rec = recs['700']
    assert rec['blocked'] == 20 * 1000
    assert rec['unblocked'] == 50000 - 20000


def test_balance_snapshot_is_as_of_previous_week_friday(app):
    """The beginning stock position is the on-hand balance as of the AS-OF date
    -- the previous week's Friday, previous_day(start_date) -- NOT of start_date
    (the walked-back Monday) as the legacy did. For report 2026-07-06:
    start_date = Mon 2026-06-29, AS-OF = Fri 2026-06-26. A trade on the Monday
    (start_date, in the Fri->Mon gap) and any trade after it must be EXCLUDED
    from the beginning balance -- this is the legacy-bug fix."""
    conn = sqlite3.connect(app.config['DATABASE']); conn.row_factory = sqlite3.Row
    _txn(conn, 1, BANK_REF, CODE_REF, '2026-01-01', 50000)   # before Friday -> counted
    _txn(conn, 2, BANK_REF, CODE_REF, '2026-06-29', -5000)   # Monday (start_date), after Friday -> EXCLUDED (the fix)
    _txn(conn, 3, BANK_REF, CODE_REF, '2026-07-03', -20000)  # after start_date, before report -> excluded

    recs = position_records(conn, BANK_REF, BANK_ID, CCY_ID, date(2026, 7, 6))
    conn.close()

    assert recs['700']['balance'] == 50000


def test_moving_average_engine_buy_sell_reset():
    """Pure moving-average cost engine: buys add full amount; a sell removes a
    proportional slice (cost * |qty| / prior balance); cost resets at balance 0."""
    from ltv_app.blueprints.ltv_stocks.legacy_port.positions_calc import _moving_average_engine

    def row(q, p):
        return {'quantity': q, 'price': p, 'brokerage': 0, 'commission': 0,
                'foreign_charge': 0, 'stamp_duty': 0, 'misc': 0}

    out = _moving_average_engine([row(100, 10), row(100, 20), row(-100, 25), row(-100, 25)])
    # after buy100@10: bal100 cost1000; buy100@20: bal200 cost3000;
    # sell100: cost_of_sales=3000*100/200=1500 -> cost1500 bal100;
    # sell100: bal0 -> cost reset 0
    assert out[0] == (100, 1000.0)
    assert out[1] == (200, 3000.0)
    assert out[2] == (100, 1500.0)
    assert out[3] == (0, 0.0)
