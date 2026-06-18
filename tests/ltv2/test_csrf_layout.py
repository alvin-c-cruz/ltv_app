from ltv2.extensions import db
from ltv2.models.user import User


def _login(client, app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice", "password": "password123"})


def test_csrf_enabled_in_default_config():
    from ltv2 import create_app
    app = create_app("ltv2.config.DevConfig")
    assert app.config.get("WTF_CSRF_ENABLED", True) is True


def test_dashboard_requires_login(client):
    resp = client.get("/")
    # anonymous → redirected to login
    assert resp.status_code in (301, 302)


def test_dashboard_renders_for_logged_in_user(client, app):
    _login(client, app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Logout" in resp.data
