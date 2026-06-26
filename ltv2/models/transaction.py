from datetime import datetime, timezone
from decimal import Decimal
from ltv2.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    trade_date = db.Column(db.Date, nullable=False)
    value_date = db.Column(db.Date, nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey("banks.id"), nullable=False)
    stock_id = db.Column(db.Integer, db.ForeignKey("stocks.id"), nullable=False)
    transaction_type_id = db.Column(db.Integer, db.ForeignKey("transaction_types.id"), nullable=False)
    quantity = db.Column(db.Numeric, nullable=False)
    price = db.Column(db.Numeric, nullable=False)
    brokerage = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    commission = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    foreign_charge = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    stamp_duty = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    misc = db.Column(db.Numeric, nullable=False, default=0, server_default="0")
    counter_bank_id = db.Column(db.Integer, db.ForeignKey("banks.id"), nullable=True)
    comments = db.Column(db.Text, nullable=True)
    locked = db.Column(db.Boolean, nullable=False, default=False, server_default=db.text("0"))
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    bank = db.relationship("Bank", foreign_keys=[bank_id])
    counter_bank = db.relationship("Bank", foreign_keys=[counter_bank_id])
    stock = db.relationship("Stock")
    transaction_type = db.relationship("TransactionType")

    @property
    def total_charges(self) -> Decimal:
        zero = Decimal(0)
        return ((self.brokerage or zero) + (self.commission or zero)
                + (self.foreign_charge or zero) + (self.stamp_duty or zero)
                + (self.misc or zero))
