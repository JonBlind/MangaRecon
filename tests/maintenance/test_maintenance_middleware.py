import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.maintenance import middleware as maintenance


def make_request(path: str = "/mangas"):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
    )


def make_middleware():
    return maintenance.MaintenanceModeMiddleware(MagicMock())


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


@pytest.mark.asyncio
async def test_disabled_maintenance_mode_allows_request(monkeypatch):
    monkeypatch.setattr(
        maintenance.settings,
        "maintenance_mode",
        False,
    )
    expected = MagicMock()
    request = make_request()
    call_next = AsyncMock(return_value=expected)

    result = await make_middleware().dispatch(
        request,
        call_next,
    )

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_enabled_maintenance_mode_allows_health_probe(monkeypatch):
    monkeypatch.setattr(
        maintenance.settings,
        "maintenance_mode",
        True,
    )
    expected = MagicMock()
    request = make_request("/healthz")
    call_next = AsyncMock(return_value=expected)

    result = await make_middleware().dispatch(request, call_next)

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/readyz", "/mangas", "/auth/jwt/login"])
async def test_enabled_maintenance_mode_returns_deliberate_503(
    monkeypatch,
    path,
):
    monkeypatch.setattr(
        maintenance.settings,
        "maintenance_mode",
        True,
    )
    monkeypatch.setattr(
        maintenance.settings,
        "maintenance_retry_after_seconds",
        600,
    )
    call_next = AsyncMock()

    response = await make_middleware().dispatch(
        make_request(path),
        call_next,
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "600"
    assert response.headers["cache-control"] == "no-store"
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Service unavailable",
        "detail": "MAINTENANCE_MODE",
    }
    call_next.assert_not_awaited()
