import datetime as dt
import pytest
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.models.bank import Bank
from ltv2.models.stock import Stock
from ltv2.models.holiday import Holiday
from ltv2.models.transaction_type import TransactionType


def test_currency_create_and_defaults(app):
    c = Currency(code="HKD", name="Hong Kong Dollar")
    db.session.add(c); db.session.commit()
    assert c.id is not None
    assert c.is_active is True
    assert c.priority == 0


def test_currency_code_unique(app):
    db.session.add(Currency(code="HKD", name="x")); db.session.commit()
    db.session.add(Currency(code="HKD", name="y"))
    with pytest.raises(Exception):
        db.session.commit()


def test_bank_transaction_basis_default(app):
    b = Bank(bank_code="CB1", name="Citibank 1")
    db.session.add(b); db.session.commit()
    assert b.transaction_basis == "trade_date"
    assert b.is_active is True


def test_stock_currency_fk(app):
    c = Currency(code="HKD", name="x"); db.session.add(c); db.session.commit()
    s = Stock(code="700", stock_name="Tencent", currency_id=c.id)
    db.session.add(s); db.session.commit()
    assert s.currency_id == c.id


def test_holiday_unique_per_currency_date(app):
    c = Currency(code="HKD", name="x"); db.session.add(c); db.session.commit()
    d = dt.date(2026, 1, 1)
    db.session.add(Holiday(currency_id=c.id, holiday_date=d)); db.session.commit()
    db.session.add(Holiday(currency_id=c.id, holiday_date=d))
    with pytest.raises(Exception):
        db.session.commit()


def test_transaction_type_create(app):
    t = TransactionType(name="Buy (Spot)", behavior_category="increase")
    db.session.add(t); db.session.commit()
    assert t.id is not None
    assert t.behavior_category == "increase"
