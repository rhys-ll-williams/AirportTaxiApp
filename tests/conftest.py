import pytest
from fastapi.testclient import TestClient

from app.store import Store, get_store, reset_store


@pytest.fixture
def store() -> Store:
    return reset_store()


@pytest.fixture
def client(store: Store):
    from app.main import app

    with TestClient(app) as c:
        yield c
    reset_store()
