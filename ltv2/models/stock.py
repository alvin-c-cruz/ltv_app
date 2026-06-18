from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Stock(ActiveMixin, db.Model):
    __tablename__ = "stocks"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    company_name = db.Column(db.String(150))
    stock_name = db.Column(db.String(150))
    yahoo_ticker = db.Column(db.String(30))
    security_code = db.Column(db.String(30))
    currency_id = db.Column(db.Integer, db.ForeignKey("currencies.id"))
    currency = db.relationship("Currency")
