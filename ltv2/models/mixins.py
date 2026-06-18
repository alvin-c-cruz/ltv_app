from ltv2.extensions import db


class ActiveMixin:
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    @classmethod
    def query_active(cls):
        return cls.query.filter_by(is_active=True)
