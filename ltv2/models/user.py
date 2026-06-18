from datetime import datetime
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from flask_login import UserMixin
from ltv2.extensions import db

_ph = PasswordHasher()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    email = db.Column(db.String(255))
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, raw: str) -> None:
        self.password_hash = _ph.hash(raw)

    def check_password(self, raw: str) -> bool:
        try:
            return _ph.verify(self.password_hash, raw)
        except (VerifyMismatchError, InvalidHashError):
            return False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
