from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from backend.dependencies import settings as db_settings
from backend.main import create_app


def _to_sync_url(url: str) -> str:
    replacements = {
        "postgresql+asyncpg://": "postgresql+psycopg://",
        "postgresql+psycopg_async://": "postgresql+psycopg://",
    }
    for async_prefix, sync_prefix in replacements.items():
        if url.startswith(async_prefix):
            return url.replace(async_prefix, sync_prefix, 1)
    return url


def _require_test_url(name: str, url: str | None) -> str:
    assert url is not None, f"{name} DB URL is missing"
    assert "manga_test" in url.lower(), (
        f"Refusing to run integration tests because {name} is not using "
        f"the expected test database: {url}"
    )
    return url


@pytest.fixture(scope="session")
def database_urls() -> dict[str, str]:
    return {
        "user_write": _require_test_url("user_write", db_settings.user_write),
        "user_read": _require_test_url("user_read", db_settings.user_read),
        "manga_write": _require_test_url("manga_write", db_settings.manga_write),
        "manga_read": _require_test_url("manga_read", db_settings.manga_read),
    }


@pytest.fixture(scope="session")
def user_write_engine(database_urls: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(
        _to_sync_url(database_urls["user_write"]),
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def manga_write_engine(database_urls: dict[str, str]) -> Iterator[Engine]:
    engine = create_engine(
        _to_sync_url(database_urls["manga_write"]),
        pool_pre_ping=True,
    )
    yield engine
    engine.dispose()


def _clean_user_domain(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                '''
                TRUNCATE TABLE
                    rating,
                    manga_collection,
                    collection,
                    "user"
                RESTART IDENTITY CASCADE
                '''
            )
        )


def _clean_manga_domain(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                '''
                TRUNCATE TABLE
                    manga_genre,
                    manga_tag,
                    manga_demographic,
                    manga_author,
                    manga,
                    genre,
                    tag,
                    demographic,
                    author
                RESTART IDENTITY CASCADE
                '''
            )
        )


@pytest.fixture(autouse=True)
def clean_test_database(
    user_write_engine: Engine,
    manga_write_engine: Engine,
) -> Iterator[None]:
    # Clean before each test so a previously interrupted run cannot leak state.
    _clean_user_domain(user_write_engine)
    _clean_manga_domain(manga_write_engine)

    yield

    # User-owned rows reference manga rows, so clean them first.
    _clean_user_domain(user_write_engine)
    _clean_manga_domain(manga_write_engine)


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_factory(app: FastAPI) -> Iterator[Callable[[], TestClient]]:
    clients: list[TestClient] = []

    def factory() -> TestClient:
        test_client = TestClient(app)
        test_client.__enter__()
        clients.append(test_client)
        return test_client

    yield factory

    for test_client in reversed(clients):
        test_client.__exit__(None, None, None)
