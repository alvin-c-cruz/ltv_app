from pytest import mark


@mark.trades_done
class TransactionsTests:
    @mark.log_out
    @mark.skip
    def test_transactions_get_not_logged_in(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/transactions' page received a GET request and there's no users logged in
        THEN check that '405' status code is returned
        """
        response = test_client.get('/transactions/')
        assert response.status_code == 302
        assert b'Login' in response.data

    @mark.log_in
    def test_transactions_get_logged_in(self, test_client_logged_in):
        """
        GIVEN a FLASK application
        WHEN the '/transactions' page received a GET request and there a user logged in
        THEN check that '200' status code is returned
        """
        response = test_client_logged_in.get('/transactions/')
        assert response.status_code == 200
        assert b'Trades Done' in response.data

