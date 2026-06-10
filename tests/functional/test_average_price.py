"""Functional tests for /trades/average_price/<bank_ref>/<code_ref>.

Returns the From account's unrounded average cost and share balance for a
stock as of a trade date — used by the Add Transfer modal to auto-fill the
price and warn on insufficient shares.
"""
TEST_DATE  = '2026-05-18'
PRIOR_DATE = '2026-05-01'
URL = '/trades/average_price/1/1'


def _insert(db_conn, **overrides):
    params = {
        'trade_date': TEST_DATE, 'value_date': TEST_DATE,
        'bank_ref': 1, 'code_ref': 1,
        'transaction_type': 'Buy (Spot)', 'quantity': 1000, 'price': 10.0,
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


class AveragePriceTests:

    def test_requires_login(self, client):
        response = client.get(URL)
        assert response.status_code == 302

    def test_unknown_refs_return_404(self, auth_client):
        response = auth_client.get('/trades/average_price/999/999')
        assert response.status_code == 404

    def test_unrounded_average_and_balance(self, auth_client, db_conn):
        _insert(db_conn, quantity=1000, price=10.0)
        _insert(db_conn, quantity=500, price=11.0)
        data = auth_client.get(f'{URL}?trade_date={TEST_DATE}').get_json()
        assert data['average'] == 15500 / 1500     # full precision, no rounding
        assert data['balance'] == 1500

    def test_trade_date_cutoff(self, auth_client, db_conn):
        _insert(db_conn, trade_date=PRIOR_DATE, value_date=PRIOR_DATE,
                quantity=1000, price=10.0)
        _insert(db_conn, quantity=500, price=11.0)   # after PRIOR_DATE
        data = auth_client.get(f'{URL}?trade_date={PRIOR_DATE}').get_json()
        assert data['average'] == 10.0
        assert data['balance'] == 1000

    def test_no_holdings(self, auth_client):
        data = auth_client.get(f'{URL}?trade_date={TEST_DATE}').get_json()
        assert data['average'] is None
        assert data['balance'] == 0
