from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Bank(ActiveMixin, db.Model):
    __tablename__ = "banks"
    id = db.Column(db.Integer, primary_key=True)
    bank_code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    report_label = db.Column(db.String(150))
    transaction_basis = db.Column(db.String(20), nullable=False, default="trade_date")
    priority = db.Column(db.Integer, nullable=False, default=0, server_default="0")
