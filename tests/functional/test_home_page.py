from pytest import mark


@mark.home_page
class HomePageTests:
    @mark.log_out
    def test_home_page_get_not_logged_in(self, test_client):
        """
        GIVEN a FLASK application
        WHEN the '/' page received a GET request and there's no users logged in
        THEN check that '302' status code is returned
        """
        response = test_client.get('/')
        assert response.status_code == 302
        assert b'LTV' not in response.data  # TODO: Update this when home_page/home.html has real content

    @mark.log_in
    def test_home_page_get_logged_in(self, test_client_logged_in):
        """
        GIVEN a FLASK application
        WHEN the '/' page received a GET request and there a user logged in
        THEN check that '200' status code is returned
        """
        response = test_client_logged_in.get('/')
        assert response.status_code == 200
        assert b'LTV' in response.data  # TODO: Update this when home_page/home.html has real content

    @mark.log_in
    def test_home_page_post_logged_in(self, test_client_logged_in):
        """
        GIVEN a FLASK application
        WHEN the '/' page received a GET request and there a user logged in
        THEN check that '200' status code is returned
        """
        response = test_client_logged_in.get('/')
        assert response.status_code == 200
        assert b'LTV' in response.data  # TODO: Update this when home_page/home.html has real content
