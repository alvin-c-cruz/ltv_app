"""
Integration tests — Trades Done home page (/trades/).
"""


class TradesDoneHomeTests:

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get('/trades/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_authenticated_returns_200(self, auth_client):
        response = auth_client.get('/trades/')
        assert response.status_code == 200

    def test_authenticated_page_contains_trades_done(self, auth_client):
        response = auth_client.get('/trades/')
        assert b'Trades Done' in response.data
