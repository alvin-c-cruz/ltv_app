import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency


# Improvement: login helper as a pytest fixture — seeds user once per test
# and logs the client in. Uses a unique username to avoid collision with banks.
@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_curr", email="alice_curr@x.com", role="user")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"username": "alice_curr", "password": "password123"})
    return client


def test_list_requires_login(client):
    assert client.get("/currencies/").status_code in (301, 302)


def test_add_currency(logged_in_client, app):
    resp = logged_in_client.post("/currencies/add",
                                 data={"code": "HKD", "name": "HK Dollar", "priority": "1"},
                                 follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        c = Currency.query.filter_by(code="HKD").first()
        assert c is not None and c.name == "HK Dollar"


def test_add_duplicate_code_flashes_error(logged_in_client, app):
    with app.app_context():
        db.session.add(Currency(code="HKD", name="x"))
        db.session.commit()
    resp = logged_in_client.post("/currencies/add",
                                 data={"code": "HKD", "name": "dup", "priority": "0"},
                                 follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Currency.query.filter_by(code="HKD").count() == 1


def test_edit_currency(logged_in_client, app):
    with app.app_context():
        c = Currency(code="USD", name="old")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    logged_in_client.post(f"/currencies/{cid}/edit",
                          data={"code": "USD", "name": "US Dollar", "priority": "2"})
    with app.app_context():
        c = Currency.query.get(cid)
        assert c.name == "US Dollar" and c.priority == 2


def test_edit_same_code_no_error(logged_in_client, app):
    """Regression: editing a currency without changing its code must NOT flash 'already exists'."""
    with app.app_context():
        c = Currency(code="EUR", name="Euro orig")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = logged_in_client.post(f"/currencies/{cid}/edit",
                                 data={"code": "EUR", "name": "Euro updated", "priority": "5"},
                                 follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        c = Currency.query.get(cid)
        assert c.name == "Euro updated" and c.priority == 5


def test_toggle_active(logged_in_client, app):
    with app.app_context():
        c = Currency(code="JPY", name="Yen")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    # Carry show as hidden field in POST body
    resp = logged_in_client.post(f"/currencies/{cid}/toggle-active",
                                 data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        c = Currency.query.get(cid)
        assert c.is_active is False


def test_list_filters_active(logged_in_client, app):
    with app.app_context():
        db.session.add(Currency(code="HKD", name="a", is_active=True))
        db.session.add(Currency(code="USD", name="b", is_active=False))
        db.session.commit()
    active_only = logged_in_client.get("/currencies/").data
    assert b"HKD" in active_only and b"USD" not in active_only
    all_rows = logged_in_client.get("/currencies/?show=all").data
    assert b"HKD" in all_rows and b"USD" in all_rows
