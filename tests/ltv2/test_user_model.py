import pytest
from ltv2.extensions import db
from ltv2.models.user import User


def _make(app, **kw):
    u = User(username=kw.get("username", "alice"),
             email=kw.get("email", "a@example.com"),
             role=kw.get("role", "user"))
    u.set_password(kw.get("password", "password123"))
    db.session.add(u)
    db.session.commit()
    return u


def test_password_is_hashed_not_plaintext(app):
    u = _make(app, password="supersecret")
    assert u.password_hash != "supersecret"
    assert u.password_hash.startswith("$argon2")


def test_check_password(app):
    u = _make(app, password="supersecret")
    assert u.check_password("supersecret") is True
    assert u.check_password("wrong") is False


def test_role_defaults_and_is_admin(app):
    u = _make(app, role="admin")
    assert u.is_admin is True
    u2 = _make(app, username="bob", email="b@x.com", role="user")
    assert u2.is_admin is False


def test_username_unique(app):
    _make(app, username="dup", email="1@x.com")
    with pytest.raises(Exception):
        _make(app, username="dup", email="2@x.com")
