# tests/functional/test_notebook_transfers.py
import pytest
from ltv_app.blueprints.notebook.extensions.transactions import (
    get_transfers,
    get_transactions,
)


def test_get_transfers_returns_pair(db_conn):
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 1
    assert result[0]['out_bank']   == 'Citibank No. 1'
    assert result[0]['in_bank']    == 'Citibank No. 2'
    assert result[0]['quantity']   == 500
    assert result[0]['code']       == '700'
    assert result[0]['stock_name'] == 'Tencent Holdings Limited'
    assert result[0]['ccy_id']     == 'HKD'


def test_get_transfers_empty_when_no_transfers(db_conn):
    result = get_transfers(db_conn, '2026-05-18')
    assert result == []


def test_get_transfers_ignores_other_dates(db_conn):
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-17',NULL,'2026-05-19',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-17',NULL,'2026-05-19',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')
    assert result == []


def test_get_transfers_no_duplicate_for_identical_same_day_pairs(db_conn):
    # Two identical transfers (same stock/qty/date/banks) on one day.
    # Driving off Transfer-Out yields exactly one row per Transfer-Out (2),
    # never a fan-out from matching both Transfer-In rows (would be 4).
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(12,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(13,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 2
    assert {r['out_ref'] for r in result} == {10, 12}


def test_get_transactions_excludes_transfer_rows(db_conn):
    # A transfer writes a Transfer-Out on the source bank and a Transfer-In on
    # the destination bank. Neither belongs in the main transactions section
    # (they are rendered by the dedicated transfer section), so a bank whose
    # only activity is a transfer must NOT appear — otherwise it produces an
    # empty bank header in the notebook.
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(11,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transactions(db_conn, '2026-05-18')

    assert result == {}


def test_get_transactions_keeps_real_trades_but_drops_transfer(db_conn):
    # A bank with a genuine spot trade AND a transfer on the same day: the spot
    # trade still shows; the transfer bank is not added on its own.
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(20,'2026-05-18',NULL,'2026-05-20',1,1,'Buy (Spot)',1000,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(21,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(22,'2026-05-18',NULL,'2026-05-20',2,1,'Transfer-In',500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,1,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transactions(db_conn, '2026-05-18')

    # Only the source bank (with the spot trade) appears; destination bank
    # (transfer-only) does not.
    assert list(result.keys()) == ['HKD']
    assert list(result['HKD'].keys()) == ['Citibank No. 1']
    trade_types = result['HKD']['Citibank No. 1']['700']
    assert 'Buy (Spot)' in trade_types
    assert 'Transfer-Out' not in trade_types


def test_get_transfers_includes_pair_with_mismatched_partner(db_conn):
    # A Transfer-Out whose Transfer-In partner differs (here: no partner row at
    # all). It must still appear — the destination bank comes from
    # counter_bank_ref, so unmatched partners are never silently dropped.
    db_conn.execute(
        "INSERT INTO tbl_transaction VALUES "
        "(10,'2026-05-18',NULL,'2026-05-20',1,1,'Transfer-Out',-500,320.5,"
        "0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,2,NULL,0,0,0)"
    )
    db_conn.commit()

    result = get_transfers(db_conn, '2026-05-18')

    assert len(result) == 1
    assert result[0]['out_bank'] == 'Citibank No. 1'
    assert result[0]['in_bank']  == 'Citibank No. 2'
