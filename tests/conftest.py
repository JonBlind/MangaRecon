import os
os.environ["MANGARECON_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from backend.main import create_app

from backend.dependencies import settings as db_settings

for name, url in {
    "user_write": db_settings.user_write,
    "user_read": db_settings.user_read,
    "manga_write": db_settings.manga_write,
    "manga_read": db_settings.manga_read,
}.items():
    assert url is not None, f"{name} DB URL is missing"
    assert "manga_test" in url.lower(), f"{name} is not using test DB: {url}"


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(autouse=True)
def clean_test_db():
    yield

    sync_url = db_settings.user_write.replace(
        "postgresql+asyncpg://",
        "postgresql://",
    )

    engine = create_engine(sync_url)

    with engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE
                rating,
                manga_collection,
                collection,
                manga_genre,
                manga_tag,
                manga_demographic,
                manga,
                author,
                "user"
            RESTART IDENTITY CASCADE
        """))

    engine.dispose()