"""
Integration tests — Authentication (login / logout).
"""


class LoginTests:

    # ── GET login page ───────────────────────────────────────────────────────

    def test_login_page_loads(self, client):
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data

    # ── POST with missing / empty credentials ────────────────────────────────

    def test_no_data_returns_login_page(self, client):
        response = client.post('/login', data={})
        assert response.status_code == 200
        assert b'Login' in response.data

    def test_no_data_shows_not_registered(self, client):
        response = client.post('/login', data={})
        assert b'User is not registered' in response.data

    def test_username_only_shows_invalid_password(self, client):
        response = client.post('/login', data={'username': 'staff_user'})
        assert response.status_code == 200
        assert b'Invalid password' in response.data

    def test_password_only_shows_not_registered(self, client):
        response = client.post('/login', data={'password': 'staffpass'})
        assert response.status_code == 200
        assert b'User is not registered' in response.data

    # ── POST with wrong credentials ──────────────────────────────────────────

    def test_unknown_user_shows_not_registered(self, client):
        response = client.post('/login', data={'username': 'nobody', 'password': 'x'})
        assert response.status_code == 200
        assert b'User is not registered' in response.data

    def test_wrong_password_shows_invalid_password(self, client):
        response = client.post('/login', data={'username': 'staff_user', 'password': 'wrong'})
        assert response.status_code == 200
        assert b'Invalid password' in response.data

    def test_wrong_password_repopulates_username(self, client):
        response = client.post('/login', data={'username': 'staff_user', 'password': 'wrong'})
        assert b'staff_user' in response.data

    # ── POST with correct credentials ────────────────────────────────────────

    def test_correct_credentials_redirects(self, client):
        response = client.post('/login', data={'username': 'staff_user', 'password': 'staffpass'})
        assert response.status_code == 302

    def test_correct_credentials_redirects_to_home(self, client):
        response = client.post('/login', data={'username': 'staff_user', 'password': 'staffpass'})
        assert '/' in response.headers['Location']

    def test_correct_credentials_follow_redirect_loads_home(self, client):
        response = client.post('/login', data={'username': 'staff_user', 'password': 'staffpass'},
                               follow_redirects=True)
        assert response.status_code == 200

    # ── Logout ───────────────────────────────────────────────────────────────

    def test_logout_redirects_to_login(self, auth_client):
        response = auth_client.get('/logout')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_logout_clears_session(self, auth_client):
        auth_client.get('/logout')
        response = auth_client.get('/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']
