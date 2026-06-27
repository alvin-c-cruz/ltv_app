"""Regression tests for the currency-aware next-banking-day endpoint."""
import json


def _next(auth_client, code_ref, trade_date, days=1):
    resp = auth_client.get(
        f'/trades/api/next-banking-day?code_ref={code_ref}'
        f'&trade_date={trade_date}&days={days}'
    )
    assert resp.status_code == 200
    return json.loads(resp.data)['value_date']


def test_one_banking_day_normal_weekday(auth_client):
    # 2026-06-29 is a Monday; +1 banking day -> Tuesday 2026-06-30
    assert _next(auth_client, 1, '2026-06-29') == '2026-06-30'


def test_one_banking_day_skips_weekend(auth_client):
    # 2026-07-03 is a Friday; +1 banking day -> Monday 2026-07-06
    assert _next(auth_client, 1, '2026-07-03') == '2026-07-06'


def test_one_banking_day_skips_currency_holiday(auth_client, db_conn):
    # Seed a HKD (ccy_ref=1) holiday on Tue 2026-06-30.
    db_conn.execute(
        "INSERT INTO tbl_holiday (holi_date, ccy_ref) VALUES ('2026-06-30', 1)"
    )
    db_conn.commit()
    # From Mon 2026-06-29, +1 banking day skips the holiday -> Wed 2026-07-01
    assert _next(auth_client, 1, '2026-06-29') == '2026-07-01'
