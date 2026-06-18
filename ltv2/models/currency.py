from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class Currency(ActiveMixin, db.Model):
    __tablename__ = "currencies"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100))
    priority = db.Column(db.Integer, nullable=False, default=0)
