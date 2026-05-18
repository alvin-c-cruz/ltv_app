from pytest import mark
from flask import url_for, request


@mark.auth
class LoginTests:
    @mark.log_out
    def test_login_page_get_start_up(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a GET request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.get('/auth/login')
        assert response.status_code == 200
        assert b'Login' in response.data

    @mark.log_out
    def test_login_page_post_typed_no_data(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.post('/auth/login', data={})
        assert response.status_code == 200
        assert b'Login' in response.data

    @mark.log_out
    def test_login_page_post_typed_username_only(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '500' status code is returned
        """
        response = test_client.post('/auth/login', data={"username": "alvin"})
        assert response.status_code == 500

    @mark.log_out
    def test_login_page_post_typed_password_only(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.post('/auth/login', data={"password": "saguiguilid"})
        assert response.status_code == 200
        assert b'Login' in response.data

    @mark.log_out
    def test_login_page_post_typed_wrong_credentials(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.post('/auth/login', data={"username": "fake_user", "password": "fake_password"})
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'User is not registered' in response.data

    @mark.log_out
    def test_login_page_post_typed_wrong_password(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.post('/auth/login', data={"username": "alvin", "password": "fake_password"})
        assert response.status_code == 200
        assert b'Login' in response.data
        assert b'Invalid password' in response.data
        assert b'alvin' in response.data

    @mark.log_out
    def test_login_page_post_typed_correct_credentials(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/auth/login' page received a POST request and there's no user logged in
        THEN check that '200' status code is returned
        """
        response = test_client.post('/auth/login', data={"username": "alvin", "password": "saguiguilid"},
                                    follow_redirects=True)
        assert response.status_code == 200
        assert request.path == url_for('home_page.home')

# TODO: Test on /auth
# TODO: Test on /logout
