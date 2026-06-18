from ltv2.extensions import db
from ltv2.models.mixins import ActiveMixin


class TransactionType(ActiveMixin, db.Model):
    __tablename__ = "transaction_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    behavior_category = db.Column(db.String(20), nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=0)
