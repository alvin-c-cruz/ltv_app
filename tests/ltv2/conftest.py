import pytest
from ltv2 import create_app
from ltv2.extensions import db as _db


@pytest.fixture
def app():
    app = create_app("ltv2.config.TestConfig")
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
