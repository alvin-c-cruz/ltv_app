from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Holiday(ActiveMixin, db.Model):
    __tablename__ = "holidays"
    __table_args__ = (db.UniqueConstraint("currency_id", "holiday_date", name="uq_holiday_ccy_date"),)
    id = db.Column(db.Integer, primary_key=True)
    currency_id = db.Column(db.Integer, db.ForeignKey("currencies.id"), nullable=False)
    holiday_date = db.Column(db.Date, nullable=False)
    currency = db.relationship("Currency")
