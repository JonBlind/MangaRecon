import os
os.environ["MANGARECON_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient
from backend.main import create_app

@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client