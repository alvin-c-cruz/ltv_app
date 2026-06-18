from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency


def _login(client, app):
    u = User(username="alice", email="a@x.com", role="user")
    u.set_password("password123")
    db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice", "password": "password123"})


def test_list_requires_login(client):
    assert client.get("/currencies/").status_code in (301, 302)


def test_add_currency(client, app):
    _login(client, app)
    resp = client.post("/currencies/add",
                       data={"code": "HKD", "name": "HK Dollar", "priority": "1"},
                       follow_redirects=True)
    assert resp.status_code == 200
    c = Currency.query.filter_by(code="HKD").first()
    assert c is not None and c.name == "HK Dollar"


def test_add_duplicate_code_flashes_error(client, app):
    _login(client, app)
    db.session.add(Currency(code="HKD", name="x")); db.session.commit()
    resp = client.post("/currencies/add",
                       data={"code": "HKD", "name": "dup", "priority": "0"},
                       follow_redirects=True)
    assert b"already exists" in resp.data
    assert Currency.query.filter_by(code="HKD").count() == 1


def test_edit_currency(client, app):
    _login(client, app)
    c = Currency(code="USD", name="old"); db.session.add(c); db.session.commit()
    client.post(f"/currencies/{c.id}/edit",
                data={"code": "USD", "name": "US Dollar", "priority": "2"})
    db.session.refresh(c)
    assert c.name == "US Dollar" and c.priority == 2


def test_toggle_active(client, app):
    _login(client, app)
    c = Currency(code="JPY", name="Yen"); db.session.add(c); db.session.commit()
    client.post(f"/currencies/{c.id}/toggle-active")
    db.session.refresh(c)
    assert c.is_active is False


def test_list_filters_active(client, app):
    _login(client, app)
    db.session.add(Currency(code="HKD", name="a", is_active=True))
    db.session.add(Currency(code="USD", name="b", is_active=False))
    db.session.commit()
    active_only = client.get("/currencies/").data
    assert b"HKD" in active_only and b"USD" not in active_only
    all_rows = client.get("/currencies/?show=all").data
    assert b"HKD" in all_rows and b"USD" in all_rows
