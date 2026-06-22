import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency
from ltv2.models.stock import Stock


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_stk", email="s@x.com", role="user")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"username": "alice_stk", "password": "password123"})
    return client


def _currency(app, code="HKD"):
    with app.app_context():
        c = Currency(code=code, name=code)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_list_requires_login(client):
    assert client.get("/stocks/").status_code in (301, 302)


def test_add_stock(logged_in_client, app):
    cid = _currency(app)
    resp = logged_in_client.post("/stocks/add", data={
        "code": "700", "company_name": "Tencent Holdings", "stock_name": "Tencent",
        "yahoo_ticker": "0700.HK", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        s = Stock.query.filter_by(code="700").first()
        assert s is not None and s.currency_id == cid


def test_add_duplicate_code_flashes(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Stock(code="700", stock_name="x", currency_id=cid))
        db.session.commit()
    resp = logged_in_client.post("/stocks/add", data={
        "code": "700", "company_name": "", "stock_name": "dup",
        "yahoo_ticker": "", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Stock.query.filter_by(code="700").count() == 1


def test_edit_stock(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="5", stock_name="old", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    logged_in_client.post(f"/stocks/{sid}/edit", data={
        "code": "5", "company_name": "HSBC Holdings", "stock_name": "HSBC",
        "yahoo_ticker": "0005.HK", "security_code": "", "currency_id": str(cid),
    })
    with app.app_context():
        s = db.session.get(Stock, sid)
        assert s.stock_name == "HSBC"


def test_edit_same_code_no_error(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="9", stock_name="orig", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    resp = logged_in_client.post(f"/stocks/{sid}/edit", data={
        "code": "9", "company_name": "", "stock_name": "renamed",
        "yahoo_ticker": "", "security_code": "", "currency_id": str(cid),
    }, follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        assert db.session.get(Stock, sid).stock_name == "renamed"


def test_toggle_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        s = Stock(code="1", stock_name="CKH", currency_id=cid)
        db.session.add(s); db.session.commit()
        sid = s.id
    resp = logged_in_client.post(f"/stocks/{sid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Stock, sid).is_active is False


def test_list_filters_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Stock(code="700", stock_name="a", currency_id=cid, is_active=True))
        db.session.add(Stock(code="5", stock_name="b", currency_id=cid, is_active=False))
        db.session.commit()
    active = logged_in_client.get("/stocks/").data
    assert b"700" in active and b">5<" not in active
    allrows = logged_in_client.get("/stocks/?show=all").data
    assert b"700" in allrows and b">5<" in allrows
