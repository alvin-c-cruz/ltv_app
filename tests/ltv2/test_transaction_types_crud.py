import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.transaction_type import TransactionType


@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_tt", email="t@x.com", role="user")
        u.set_password("password123")
        db.session.add(u); db.session.commit()
    client.post("/login", data={"username": "alice_tt", "password": "password123"})
    return client


def test_list_requires_login(client):
    assert client.get("/transaction-types/").status_code in (301, 302)


def test_add_transaction_type(logged_in_client, app):
    resp = logged_in_client.post("/transaction-types/add", data={
        "name": "Buy (Spot)", "behavior_category": "increase", "priority": "1"},
        follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        t = TransactionType.query.filter_by(name="Buy (Spot)").first()
        assert t is not None and t.behavior_category == "increase"


def test_invalid_behavior_category_rejected(logged_in_client, app):
    logged_in_client.post("/transaction-types/add", data={
        "name": "Bogus", "behavior_category": "explode", "priority": "0"})
    with app.app_context():
        assert TransactionType.query.filter_by(name="Bogus").first() is None


def test_add_duplicate_name_flashes(logged_in_client, app):
    with app.app_context():
        db.session.add(TransactionType(name="Sell (Spot)", behavior_category="decrease"))
        db.session.commit()
    resp = logged_in_client.post("/transaction-types/add", data={
        "name": "Sell (Spot)", "behavior_category": "decrease", "priority": "0"},
        follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert TransactionType.query.filter_by(name="Sell (Spot)").count() == 1


def test_edit_transaction_type(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Transfer-Out", behavior_category="transfer_out")
        db.session.add(t); db.session.commit()
        tid = t.id
    logged_in_client.post(f"/transaction-types/{tid}/edit", data={
        "name": "Transfer-Out", "behavior_category": "transfer_out", "priority": "5"})
    with app.app_context():
        assert db.session.get(TransactionType, tid).priority == 5


def test_edit_same_name_no_error(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Dividend", behavior_category="dividend")
        db.session.add(t); db.session.commit()
        tid = t.id
    resp = logged_in_client.post(f"/transaction-types/{tid}/edit", data={
        "name": "Dividend", "behavior_category": "dividend", "priority": "2"},
        follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        assert db.session.get(TransactionType, tid).priority == 2


def test_toggle_active(logged_in_client, app):
    with app.app_context():
        t = TransactionType(name="Neutral Adj", behavior_category="neutral")
        db.session.add(t); db.session.commit()
        tid = t.id
    resp = logged_in_client.post(f"/transaction-types/{tid}/toggle-active", data={"show": "active"})
    assert "show=active" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(TransactionType, tid).is_active is False
