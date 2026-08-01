from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx2
import pytest

from backend.clients import mangaupdates as mangaupdates_module
from backend.clients.mangaupdates import (
    MangaUpdatesClient,
    MangaUpdatesHTTPError,
    MangaUpdatesInvalidResponseError,
    MangaUpdatesRateLimitError,
    MangaUpdatesTransportError,
    MangaUpdatesUnavailableError,
)


def make_client(
    handler,
    *,
    min_request_interval_seconds: float = 0.0,
) -> MangaUpdatesClient:
    return MangaUpdatesClient(
        base_url="https://api.mangaupdates.com/v1",
        timeout_seconds=5.0,
        min_request_interval_seconds=(
            min_request_interval_seconds
        ),
        user_agent="MangaRecon-Test/0.1",
        transport=httpx2.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_search_series_sends_expected_request() -> None:
    captured_request: httpx2.Request | None = None

    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        nonlocal captured_request
        captured_request = request

        return httpx2.Response(
            200,
            json={
                "total_hits": 1,
                "results": [
                    {
                        "record": {
                            "series_id": 123,
                            "title": "Berserk",
                        }
                    }
                ],
            },
        )

    async with make_client(handler) as client:
        result = await client.search_series(
            "  Berserk  ",
            page=2,
            per_page=10,
        )

    assert result["total_hits"] == 1
    assert captured_request is not None
    assert captured_request.method == "POST"
    assert captured_request.url.path == (
        "/v1/series/search"
    )
    assert captured_request.headers["accept"] == (
        "application/json"
    )
    assert captured_request.headers["user-agent"] == (
        "MangaRecon-Test/0.1"
    )
    assert json.loads(captured_request.content) == {
        "search": "Berserk",
        "page": 2,
        "perpage": 10,
    }


@pytest.mark.asyncio
async def test_get_series_sends_series_id_and_option() -> None:
    captured_request: httpx2.Request | None = None

    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        nonlocal captured_request
        captured_request = request

        return httpx2.Response(
            200,
            json={
                "series_id": 123,
                "title": "Berserk",
            },
        )

    async with make_client(handler) as client:
        result = await client.get_series(
            123,
            unrendered_fields=True,
        )

    assert result == {
        "series_id": 123,
        "title": "Berserk",
    }
    assert captured_request is not None
    assert captured_request.method == "GET"
    assert captured_request.url.path == "/v1/series/123"
    assert captured_request.url.params[
        "unrenderedFields"
    ] == "true"


@pytest.mark.asyncio
async def test_rate_limit_error_preserves_retry_after() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            429,
            headers={
                "Retry-After": "5",
            },
            json={
                "message": "Too many requests",
            },
        )

    async with make_client(handler) as client:
        with pytest.raises(
            MangaUpdatesRateLimitError
        ) as exc_info:
            await client.get_series(123)

    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == "5"


@pytest.mark.asyncio
async def test_server_error_is_normalized() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            503,
            json={
                "message": "Unavailable",
            },
        )

    async with make_client(handler) as client:
        with pytest.raises(
            MangaUpdatesUnavailableError
        ) as exc_info:
            await client.get_series(123)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_other_http_error_is_normalized() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            404,
            json={
                "message": "Not found",
            },
        )

    async with make_client(handler) as client:
        with pytest.raises(
            MangaUpdatesHTTPError
        ) as exc_info:
            await client.get_series(123)

    assert type(exc_info.value) is MangaUpdatesHTTPError
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_transport_error_is_normalized() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise httpx2.ConnectError(
            "Connection failed",
            request=request,
        )

    async with make_client(handler) as client:
        with pytest.raises(
            MangaUpdatesTransportError
        ):
            await client.get_series(123)


@pytest.mark.asyncio
async def test_invalid_json_is_normalized() -> None:
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

    async with make_client(handler) as client:
        with pytest.raises(
            MangaUpdatesInvalidResponseError
        ):
            await client.get_series(123)


@pytest.mark.asyncio
async def test_requests_are_spaced_apart(
    monkeypatch,
) -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "series_id": 123,
            },
        )

    clock_values = iter(
        [
            0.0,
            0.25,
            1.0,
        ]
    )
    sleep_mock = AsyncMock()

    monkeypatch.setattr(
        mangaupdates_module,
        "monotonic",
        lambda: next(clock_values),
    )
    monkeypatch.setattr(
        mangaupdates_module,
        "sleep",
        sleep_mock,
    )

    async with make_client(
        handler,
        min_request_interval_seconds=1.0,
    ) as client:
        await client.get_series(123)
        await client.get_series(124)

    sleep_mock.assert_awaited_once()

    delay = sleep_mock.await_args.args[0]
    assert delay == pytest.approx(0.75)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "page", "per_page"),
    [
        ("   ", 1, 25),
        ("Berserk", 0, 25),
        ("Berserk", 1, 0),
    ],
)
async def test_search_rejects_invalid_arguments(
    query: str,
    page: int,
    per_page: int,
) -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise AssertionError(
            "No HTTP request should be sent."
        )

    async with make_client(handler) as client:
        with pytest.raises(ValueError):
            await client.search_series(
                query,
                page=page,
                per_page=per_page,
            )


@pytest.mark.asyncio
async def test_get_series_rejects_invalid_id() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise AssertionError(
            "No HTTP request should be sent."
        )

    async with make_client(handler) as client:
        with pytest.raises(ValueError):
            await client.get_series(0)


@pytest.mark.parametrize(
    (
        "timeout_seconds",
        "min_request_interval_seconds",
    ),
    [
        (0.0, 1.0),
        (10.0, -1.0),
    ],
)
def test_client_rejects_invalid_configuration(
    timeout_seconds: float,
    min_request_interval_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        MangaUpdatesClient(
            timeout_seconds=timeout_seconds,
            min_request_interval_seconds=(
                min_request_interval_seconds
            ),
        )