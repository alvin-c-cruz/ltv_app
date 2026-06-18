from ltv2.extensions import db
from ltv2.models.user import User


def _seed(app, username, role):
    u = User(username=username, email="x@x.com", role=role)
    u.set_password("password123")
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, username):
    client.post("/login", data={"username": username, "password": "password123"})


def test_admin_can_access(client, app):
    _seed(app, "boss", "admin")
    _login(client, "boss")
    assert client.get("/admin/ping").status_code == 200


def test_user_forbidden(client, app):
    _seed(app, "joe", "user")
    _login(client, "joe")
    assert client.get("/admin/ping").status_code == 403


def test_anonymous_redirected(client, app):
    assert client.get("/admin/ping").status_code == 302
