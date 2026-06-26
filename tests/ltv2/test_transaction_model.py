from datetime import date
from decimal import Decimal
from ltv2.extensions import db
from ltv2.models.currency import Currency
from ltv2.models.bank import Bank
from ltv2.models.stock import Stock
from ltv2.models.transaction_type import TransactionType
from ltv2.models.transaction import Transaction


def _seed(app):
    with app.app_context():
        ccy = Currency(code="HKD")
        bank = Bank(bank_code="B1", name="Bank One")
        stock = Stock(code="700")
        tt = TransactionType(name="Buy (Spot)", behavior_category="increase", book="long")
        db.session.add_all([ccy, bank, stock, tt])
        db.session.commit()
        return bank.id, stock.id, tt.id


def test_total_charges_sums_all_charge_fields(app):
    bank_id, stock_id, tt_id = _seed(app)
    with app.app_context():
        t = Transaction(
            trade_date=date(2026, 6, 1), value_date=date(2026, 6, 3),
            bank_id=bank_id, stock_id=stock_id, transaction_type_id=tt_id,
            quantity=Decimal("100"), price=Decimal("10"),
            brokerage=Decimal("1"), commission=Decimal("2"),
            foreign_charge=Decimal("3"), stamp_duty=Decimal("4"), misc=Decimal("5"),
        )
        db.session.add(t); db.session.commit()
        assert t.total_charges == Decimal("15")


def test_charge_fields_default_to_zero(app):
    bank_id, stock_id, tt_id = _seed(app)
    with app.app_context():
        t = Transaction(
            trade_date=date(2026, 6, 1), value_date=date(2026, 6, 3),
            bank_id=bank_id, stock_id=stock_id, transaction_type_id=tt_id,
            quantity=Decimal("50"), price=Decimal("20"),
        )
        db.session.add(t); db.session.commit()
        assert t.total_charges == Decimal("0")
        assert t.locked is False
