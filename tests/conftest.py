import os
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["MANGARECON_ENV"] = "test"

from backend.db import client_db as client_db_module
from backend.main import create_app


@pytest.fixture(autouse=True)
def first_database_timing_already_claimed(monkeypatch):
    """Keep process-scoped production timing from leaking between tests."""
    monkeypatch.setattr(
        client_db_module,
        "_first_database_execute_pending",
        False,
    )


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
