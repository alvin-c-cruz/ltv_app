import datetime as dt
import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.currency import Currency
from ltv2.models.holiday import Holiday


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_hol", email="h@x.com", role="user")
        u.set_password("password123")
        db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice_hol", "password": "password123"})
    return client


def _currency(app, code="HKD"):
    with app.app_context():
        c = Currency(code=code, name=code); db.session.add(c); db.session.commit()
        return c.id


def test_list_requires_login(client):
    assert client.get("/holidays/").status_code in (301, 302)


def test_add_holiday(logged_in_client, app):
    cid = _currency(app)
    resp = logged_in_client.post("/holidays/add", data={
        "currency_id": str(cid), "holiday_date": "2026-01-01"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        h = Holiday.query.filter_by(currency_id=cid).first()
        assert h is not None and h.holiday_date == dt.date(2026, 1, 1)


def test_add_duplicate_flashes(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 1, 1)))
        db.session.commit()
    resp = logged_in_client.post("/holidays/add", data={
        "currency_id": str(cid), "holiday_date": "2026-01-01"}, follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Holiday.query.filter_by(currency_id=cid).count() == 1


def test_toggle_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        h = Holiday(currency_id=cid, holiday_date=dt.date(2026, 5, 1))
        db.session.add(h); db.session.commit()
        hid = h.id
    resp = logged_in_client.post(f"/holidays/{hid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Holiday, hid).is_active is False


def test_list_filters_active(logged_in_client, app):
    cid = _currency(app)
    with app.app_context():
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 1, 1), is_active=True))
        db.session.add(Holiday(currency_id=cid, holiday_date=dt.date(2026, 2, 2), is_active=False))
        db.session.commit()
    active = logged_in_client.get("/holidays/").data
    assert b"2026-01-01" in active and b"2026-02-02" not in active
    allrows = logged_in_client.get("/holidays/?show=all").data
    assert b"2026-01-01" in allrows and b"2026-02-02" in allrows
