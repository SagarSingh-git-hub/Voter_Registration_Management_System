import pytest
import mongomock
from unittest.mock import patch, MagicMock
from config import TestConfig
from app import create_app


@pytest.fixture(scope='session')
def app():
    """Application fixture with test config. MongoDB is replaced by mongomock."""
    application = create_app(TestConfig)
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()