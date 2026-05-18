"""
Integration tests — Home page (/).
"""


class HomePageTests:

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_authenticated_returns_200(self, auth_client):
        response = auth_client.get('/')
        assert response.status_code == 200

    def test_authenticated_page_contains_ltv(self, auth_client):
        response = auth_client.get('/')
        assert b'LTV' in response.data
