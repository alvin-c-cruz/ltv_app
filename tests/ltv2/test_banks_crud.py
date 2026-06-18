import pytest
from ltv2.extensions import db
from ltv2.models.user import User
from ltv2.models.bank import Bank


# Improvement 2: login helper as a pytest fixture — seeds user once per test
# and logs the client in. Uses a unique username to avoid collision.
@pytest.fixture
def logged_in_client(client, app):
    with app.app_context():
        u = User(username="alice_banks", email="alice_banks@x.com", role="user")
        u.set_password("password123")
        db.session.add(u)
        db.session.commit()
    client.post("/login", data={"username": "alice_banks", "password": "password123"})
    return client


def test_list_requires_login(client):
    assert client.get("/banks/").status_code in (301, 302)


def test_add_bank_trade_date(logged_in_client, app):
    resp = logged_in_client.post("/banks/add", data={
        "bank_code": "CB1", "name": "Citibank 1", "report_label": "Citi 1",
        "transaction_basis": "trade_date", "priority": "1"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        b = Bank.query.filter_by(bank_code="CB1").first()
        assert b is not None and b.transaction_basis == "trade_date"


def test_add_bank_value_date(logged_in_client, app):
    resp = logged_in_client.post("/banks/add", data={
        "bank_code": "CB2", "name": "Citibank 2", "report_label": "Citi 2",
        "transaction_basis": "value_date", "priority": "2"}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        b = Bank.query.filter_by(bank_code="CB2").first()
        assert b is not None and b.transaction_basis == "value_date"


def test_add_duplicate_bank_code_flashes(logged_in_client, app):
    with app.app_context():
        db.session.add(Bank(bank_code="CB1", name="x"))
        db.session.commit()
    resp = logged_in_client.post("/banks/add", data={
        "bank_code": "CB1", "name": "dup", "transaction_basis": "trade_date",
        "priority": "0"}, follow_redirects=True)
    assert b"already exists" in resp.data
    with app.app_context():
        assert Bank.query.filter_by(bank_code="CB1").count() == 1


def test_invalid_transaction_basis_rejected(logged_in_client, app):
    logged_in_client.post("/banks/add", data={
        "bank_code": "CB9", "name": "x", "transaction_basis": "bogus",
        "priority": "0"})
    with app.app_context():
        assert Bank.query.filter_by(bank_code="CB9").first() is None


def test_edit_bank(logged_in_client, app):
    with app.app_context():
        b = Bank(bank_code="DB1", name="old")
        db.session.add(b)
        db.session.commit()
        bid = b.id
    logged_in_client.post(f"/banks/{bid}/edit", data={
        "bank_code": "DB1", "name": "Deutsche 1", "report_label": "",
        "transaction_basis": "trade_date", "priority": "3"})
    with app.app_context():
        b = Bank.query.get(bid)
        assert b.name == "Deutsche 1" and b.priority == 3


def test_edit_same_code_no_error(logged_in_client, app):
    """Regression: editing a bank without changing bank_code must NOT flash 'already exists'."""
    with app.app_context():
        b = Bank(bank_code="HS1", name="HSBC orig")
        db.session.add(b)
        db.session.commit()
        bid = b.id
    resp = logged_in_client.post(f"/banks/{bid}/edit", data={
        "bank_code": "HS1", "name": "HSBC updated", "report_label": "",
        "transaction_basis": "trade_date", "priority": "5"}, follow_redirects=True)
    assert b"already exists" not in resp.data
    with app.app_context():
        b = Bank.query.get(bid)
        assert b.name == "HSBC updated" and b.priority == 5


def test_toggle_active(logged_in_client, app):
    with app.app_context():
        b = Bank(bank_code="MS1", name="Morgan")
        db.session.add(b)
        db.session.commit()
        bid = b.id
    # Improvement 3: carry show as hidden field in POST body
    logged_in_client.post(f"/banks/{bid}/toggle-active",
                          data={"show": "active"})
    with app.app_context():
        b = Bank.query.get(bid)
        assert b.is_active is False


def test_list_filters_active(logged_in_client, app):
    with app.app_context():
        db.session.add(Bank(bank_code="ACT", name="Active Bank", is_active=True))
        db.session.add(Bank(bank_code="INA", name="Inactive Bank", is_active=False))
        db.session.commit()
    active_only = logged_in_client.get("/banks/").data
    assert b"ACT" in active_only and b"INA" not in active_only
    all_rows = logged_in_client.get("/banks/?show=all").data
    assert b"ACT" in all_rows and b"INA" in all_rows
