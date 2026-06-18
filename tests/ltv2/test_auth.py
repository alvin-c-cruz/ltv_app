from ltv2.extensions import db
from ltv2.models.user import User


def _seed(app, username="alice", password="password123", role="user"):
    u = User(username=username, email="a@x.com", role=role)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    return u


def test_login_success_redirects(client, app):
    _seed(app)
    resp = client.post("/login", data={"username": "alice", "password": "password123"})
    assert resp.status_code == 302
    assert "/" in resp.headers["Location"]


def test_login_wrong_password_shows_error(client, app):
    _seed(app)
    resp = client.post("/login", data={"username": "alice", "password": "nope"},
                       follow_redirects=True)
    assert b"Invalid username or password" in resp.data


def test_logout(client, app):
    _seed(app)
    client.post("/login", data={"username": "alice", "password": "password123"})
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
