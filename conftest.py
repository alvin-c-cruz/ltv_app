import os
import sys

# ltv_app now lives under applications/ — make it importable before it is imported below.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'applications'))

from pytest import fixture
from ltv_app import create_app


@fixture(scope='function')
def test_client():
    flask_app = create_app()

    with flask_app.test_client() as test_client:
        yield test_client


@fixture(scope='function')
def test_client_logged_in():
    flask_app = create_app()

    with flask_app.test_client() as test_client:
        test_client.post('/auth/login', data={"username": "admin", "password": "ac1123581321"})
        yield test_client
