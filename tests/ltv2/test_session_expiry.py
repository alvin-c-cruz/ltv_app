from datetime import timedelta


def test_lifetime_configured(app):
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(minutes=60)


def test_session_marked_permanent_on_request(client):
    client.get("/")
    with client.session_transaction() as sess:
        assert sess.permanent is True
