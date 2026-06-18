from datetime import datetime, timedelta
from ltv2.extensions import db
from ltv2.models.user import User


def _seed(app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    return u


def test_lock_after_five_failures(client, app):
    _seed(app)
    for _ in range(5):
        client.post("/login", data={"username": "alice", "password": "wrong"})
    # correct password now refused because locked
    resp = client.post("/login", data={"username": "alice", "password": "password123"},
                       follow_redirects=True)
    assert b"locked" in resp.data.lower()
    u = User.query.filter_by(username="alice").first()
    assert u.locked_until is not None

def test_success_resets_counter(client, app):
    u = _seed(app)
    for _ in range(2):
        client.post("/login", data={"username": "alice", "password": "wrong"})
    client.post("/login", data={"username": "alice", "password": "password123"})
    u = User.query.filter_by(username="alice").first()
    assert u.failed_logins == 0
    assert u.locked_until is None

def test_lock_expires(client, app):
    u = _seed(app)
    u.locked_until = datetime.utcnow() - timedelta(minutes=1)  # already expired
    u.failed_logins = 5
    db.session.commit()
    resp = client.post("/login", data={"username": "alice", "password": "password123"})
    assert resp.status_code == 302  # allowed through
