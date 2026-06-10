"""Functional tests for the printable Trades Done report (popup).

GET /trades/print_with_gain_loss/<trade_date> renders an HTML equivalent of
the New Trades Done Excel file. Gain/loss cells appear only for Sell (Spot).
"""
TEST_DATE  = '2026-05-18'
PRIOR_DATE = '2026-05-01'
PRINT_URL  = f'/trades/print_with_gain_loss/{TEST_DATE}'


def _insert_transaction(db_conn, **overrides):
    params = {
        'trade_date': TEST_DATE, 'value_date': '2026-05-20',
        'bank_ref': 1, 'code_ref': 1,
        'transaction_type': 'Buy (Spot)', 'quantity': 1000, 'price': 320.50,
        'brokerage': 0, 'commission': 0, 'foreign_charge': 0,
        'stamp_duty': 0, 'misc': 0, 'locked': 0,
    }
    params.update(overrides)
    db_conn.execute(
        """INSERT INTO tbl_transaction
           (trade_date, value_date, bank_ref, code_ref, transaction_type,
            quantity, price, brokerage, commission, foreign_charge,
            stamp_duty, misc, locked)
           VALUES (:trade_date, :value_date, :bank_ref, :code_ref,
                   :transaction_type, :quantity, :price, :brokerage,
                   :commission, :foreign_charge, :stamp_duty, :misc, :locked)""",
        params,
    )
    db_conn.commit()


class PrintTradesDoneTests:

    def test_requires_login(self, client):
        response = client.get(PRINT_URL)
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_no_data_redirects_with_flash(self, auth_client):
        response = auth_client.get(PRINT_URL, follow_redirects=True)
        assert b'No data to print' in response.data

    def test_buy_shows_average_without_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'BUY' in response.data
        assert b'320.5000' in response.data          # average on last buy row
        assert b'Cost HKD' not in response.data

    def test_sell_spot_shows_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn, trade_date=PRIOR_DATE, value_date='2026-05-03',
                            quantity=1000, price=300.00)
        _insert_transaction(db_conn, transaction_type='Sell (Spot)',
                            quantity=-500, price=350.00)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'Cost HKD' in response.data
        assert b'150,000.00' in response.data        # 500 x 300 cost basis
        assert b'25,000.00' in response.data         # 175,000 - 150,000 gain
        assert b'Gain HKD' in response.data

    def test_sell_short_has_no_gain_loss(self, auth_client, db_conn):
        _insert_transaction(db_conn, transaction_type='Sell (Short)',
                            quantity=-500, price=310.00)
        response = auth_client.get(PRINT_URL)
        assert response.status_code == 200
        assert b'Cost HKD' not in response.data
