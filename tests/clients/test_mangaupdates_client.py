from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest

import backend.clients.mangaupdates_client as client_module
from backend.clients.mangaupdates_client import (
    MangaUpdatesClient,
    MangaUpdatesHTTPError,
    MangaUpdatesInvalidResponseError,
    MangaUpdatesRateLimitError,
    MangaUpdatesTransportError,
    MangaUpdatesUnavailableError,
)


def make_json_transport(
    payload: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    requests: list[httpx2.Request] | None = None,
) -> httpx2.MockTransport:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        if requests is not None:
            requests.append(request)

        return httpx2.Response(
            status_code,
            json=payload,
            headers=headers,
        )

    return httpx2.MockTransport(handler)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"base_url": "   "},
            "base_url cannot be blank",
        ),
        (
            {"timeout_seconds": 0},
            "timeout_seconds must be greater than zero",
        ),
        (
            {"min_request_interval_seconds": -1},
            (
                "min_request_interval_seconds "
                "cannot be negative"
            ),
        ),
        (
            {"user_agent": "   "},
            "user_agent cannot be blank",
        ),
    ],
)
def test_constructor_rejects_invalid_configuration(
    arguments: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MangaUpdatesClient(**arguments)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_series_sends_expected_request() -> None:
    requests: list[httpx2.Request] = []
    payload = {
        "series_id": 42,
        "title": "Berserk",
    }

    async with MangaUpdatesClient(
        base_url="https://api.example/v1/",
        min_request_interval_seconds=0,
        user_agent="MangaRecon-Test/1.0",
        transport=make_json_transport(
            payload,
            requests=requests,
        ),
    ) as client:
        result = await client.get_series(
            42,
            unrendered_fields=True,
        )

    assert result == payload
    assert len(requests) == 1

    request = requests[0]

    assert request.method == "GET"
    assert request.url.path == "/v1/series/42"
    assert (
        request.url.params["unrenderedFields"]
        == "true"
    )
    assert request.headers["Accept"] == (
        "application/json"
    )
    assert request.headers["User-Agent"] == (
        "MangaRecon-Test/1.0"
    )


@pytest.mark.asyncio
async def test_search_series_sends_expected_request() -> None:
    requests: list[httpx2.Request] = []
    payload = {
        "results": [],
        "page": 2,
    }

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            payload,
            requests=requests,
        ),
    ) as client:
        result = await client.search_series(
            "  Berserk  ",
            page=2,
            per_page=10,
        )

    assert result == payload
    assert len(requests) == 1

    request = requests[0]

    assert request.method == "POST"
    assert request.url.path == (
        "/v1/series/search"
    )
    assert json.loads(
        request.content.decode("utf-8")
    ) == {
        "search": "Berserk",
        "page": 2,
        "perpage": 10,
    }


@pytest.mark.asyncio
async def test_request_arguments_are_validated_before_io(
) -> None:
    requests: list[httpx2.Request] = []

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            {},
            requests=requests,
        ),
    ) as client:
        with pytest.raises(
            ValueError,
            match="series_id must be greater than zero",
        ):
            await client.get_series(0)

        with pytest.raises(
            ValueError,
            match="query cannot be blank",
        ):
            await client.search_series("   ")

        with pytest.raises(
            ValueError,
            match="page must be at least 1",
        ):
            await client.search_series(
                "Berserk",
                page=0,
            )

        with pytest.raises(
            ValueError,
            match="per_page must be at least 1",
        ):
            await client.search_series(
                "Berserk",
                per_page=0,
            )

    assert requests == []


@pytest.mark.asyncio
async def test_transport_failure_is_wrapped() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise httpx2.ConnectError(
            "connection failed",
            request=request,
        )

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=httpx2.MockTransport(handler),
    ) as client:
        with pytest.raises(
            MangaUpdatesTransportError,
            match="Could not reach MangaUpdates",
        ) as exc_info:
            await client.get_series(42)

    assert isinstance(
        exc_info.value.__cause__,
        httpx2.ConnectError,
    )


@pytest.mark.asyncio
async def test_rate_limit_response_preserves_retry_after(
) -> None:
    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            {"error": "rate limited"},
            status_code=429,
            headers={"Retry-After": "30"},
        ),
    ) as client:
        with pytest.raises(
            MangaUpdatesRateLimitError
        ) as exc_info:
            await client.get_series(42)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == "30"


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (400, MangaUpdatesHTTPError),
        (404, MangaUpdatesHTTPError),
        (500, MangaUpdatesUnavailableError),
        (503, MangaUpdatesUnavailableError),
    ],
)
@pytest.mark.asyncio
async def test_unsuccessful_status_is_classified(
    status_code: int,
    expected_exception: type[MangaUpdatesHTTPError],
) -> None:
    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            {"error": "upstream failure"},
            status_code=status_code,
        ),
    ) as client:
        with pytest.raises(
            expected_exception
        ) as exc_info:
            await client.get_series(42)

    assert exc_info.value.status_code == status_code


@pytest.mark.asyncio
async def test_invalid_json_is_rejected() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"not-json",
            headers={
                "Content-Type": "application/json",
            },
        )

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=httpx2.MockTransport(handler),
    ) as client:
        with pytest.raises(
            MangaUpdatesInvalidResponseError,
            match="invalid JSON",
        ):
            await client.get_series(42)


@pytest.mark.asyncio
async def test_non_object_json_is_rejected() -> None:
    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            ["unexpected", "list"]
        ),
    ) as client:
        with pytest.raises(
            MangaUpdatesInvalidResponseError,
            match="not an object",
        ):
            await client.get_series(42)


@pytest.mark.asyncio
async def test_requests_observe_minimum_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monotonic_values = iter(
        [
            10.0,
            10.25,
            11.0,
        ]
    )
    sleeper = AsyncMock()

    monkeypatch.setattr(
        client_module,
        "monotonic",
        lambda: next(monotonic_values),
    )
    monkeypatch.setattr(
        client_module,
        "sleep",
        sleeper,
    )

    async with MangaUpdatesClient(
        min_request_interval_seconds=1.0,
        transport=make_json_transport(
            {"series_id": 42}
        ),
    ) as client:
        await client.get_series(42)
        await client.get_series(42)

    sleeper.assert_awaited_once_with(0.75)


def test_factory_uses_runtime_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_client = object()
    constructor = MagicMock(
        return_value=configured_client
    )

    monkeypatch.setattr(
        client_module.settings,
        "mangaupdates_base_url",
        "https://configured.example/v1",
    )
    monkeypatch.setattr(
        client_module.settings,
        "mangaupdates_timeout_seconds",
        7.5,
    )
    monkeypatch.setattr(
        client_module.settings,
        "mangaupdates_min_request_interval_seconds",
        0.5,
    )
    monkeypatch.setattr(
        client_module.settings,
        "mangaupdates_user_agent",
        "Configured-Agent/1.0",
    )
    monkeypatch.setattr(
        client_module,
        "MangaUpdatesClient",
        constructor,
    )

    result = (
        client_module.create_mangaupdates_client()
    )

    assert result is configured_client
    constructor.assert_called_once_with(
        base_url="https://configured.example/v1",
        timeout_seconds=7.5,
        min_request_interval_seconds=0.5,
        user_agent="Configured-Agent/1.0",
    )