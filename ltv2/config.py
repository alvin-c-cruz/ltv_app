import os
from datetime import timedelta

_INSTANCE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance")


class Config:
    SECRET_KEY = os.environ.get("LTV2_SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(_INSTANCE, "ltv2.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    # Lockout policy
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15


class DevConfig(Config):
    DEBUG = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
