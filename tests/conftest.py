import pytest

from app import app
from inventory import reset_inventory


@pytest.fixture(autouse=True)
def fresh_inventory():
    """Give every test its own copy of the seed inventory."""
    reset_inventory()
    yield
    reset_inventory()


@pytest.fixture
def client():
    return app.test_client()
