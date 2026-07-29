from unittest.mock import AsyncMock, MagicMock

from backend.routes import system_routes


def test_healthz_returns_running_message(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"message": "MangaRecon API is running."}


def test_readyz_returns_503_when_any_dependency_is_unavailable(
    app,
    client,
    monkeypatch,
):
    cache = MagicMock()
    cache.ping = AsyncMock(return_value=True)

    monkeypatch.setattr(
        system_routes,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        system_routes,
        "database_connections_ready",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        system_routes,
        "get_redis_cache",
        MagicMock(return_value=cache),
    )
    monkeypatch.setattr(
        system_routes,
        "rate_limit_storage_ready",
        AsyncMock(return_value=True),
    )

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "error",
        "data": {},
        "message": "Service unavailable.",
        "detail": "TEMPORARILY_UNAVAILABLE",
    }
    assert response.headers["Retry-After"] == "15"

def test_readyz_returns_ready_when_every_dependency_is_available(
    app,
    client,
    monkeypatch,
):
    cache = MagicMock()
    cache.ping = AsyncMock(return_value=True)
    database_ready = AsyncMock(return_value=True)
    limiter_ready = AsyncMock(return_value=True)

    monkeypatch.setattr(
        system_routes,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        system_routes,
        "database_connections_ready",
        database_ready,
    )
    monkeypatch.setattr(
        system_routes,
        "get_redis_cache",
        MagicMock(return_value=cache),
    )
    monkeypatch.setattr(
        system_routes,
        "rate_limit_storage_ready",
        limiter_ready,
    )

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"message": "MangaRecon API is ready."}
    assert app.state.rate_limit_storage_ready is True
    database_ready.assert_awaited_once_with()
    cache.ping.assert_awaited_once_with()
    limiter_ready.assert_awaited_once_with()


def test_readyz_skips_external_checks_outside_production(
    client,
    monkeypatch,
):
    database_ready = AsyncMock()
    get_cache = MagicMock()
    limiter_ready = AsyncMock()

    monkeypatch.setattr(
        system_routes,
        "ENV",
        "test",
    )
    monkeypatch.setattr(
        system_routes,
        "database_connections_ready",
        database_ready,
    )
    monkeypatch.setattr(
        system_routes,
        "get_redis_cache",
        get_cache,
    )
    monkeypatch.setattr(
        system_routes,
        "rate_limit_storage_ready",
        limiter_ready,
    )

    response = client.get("/readyz")

    assert response.status_code == 200
    database_ready.assert_not_awaited()
    get_cache.assert_not_called()
    limiter_ready.assert_not_awaited()
