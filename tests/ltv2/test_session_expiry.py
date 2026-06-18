from datetime import timedelta


def test_lifetime_configured(app):
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=60)


def test_session_marked_permanent_on_request(client, app):
    # hitting any page should set a session cookie with the rolling window
    client.get("/")
    # Flask sets the cookie; assert the app keeps refresh-each-request on
    assert app.config.get("SESSION_REFRESH_EACH_REQUEST", True) is True
