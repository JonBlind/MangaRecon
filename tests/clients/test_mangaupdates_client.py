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
    MangaUpdatesInvalidCoverError,
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
        (
            {"max_cover_bytes": 0},
            "max_cover_bytes must be greater than zero",
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
async def test_discover_series_page_sends_filters_without_query(
) -> None:
    requests: list[httpx2.Request] = []
    payload = {
        "total_hits": 1,
        "page": 3,
        "per_page": 100,
        "results": [],
    }

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            payload,
            requests=requests,
        ),
    ) as client:
        result = await client.discover_series_page(
            page=3,
            per_page=100,
            series_types=("Manga", "Manhwa", "Manga"),
            year=" 2020 ",
            genres=("Action",),
            exclude_genres=("Hentai",),
            filters=("completed", "no_oneshots"),
            order_by="rating",
        )

    assert result == payload
    assert len(requests) == 1
    assert json.loads(
        requests[0].content.decode("utf-8")
    ) == {
        "page": 3,
        "perpage": 100,
        "orderby": "rating",
        "type": ["Manga", "Manhwa"],
        "year": "2020",
        "genre": ["Action"],
        "exclude_genre": ["Hentai"],
        "filters": ["completed", "no_oneshots"],
    }


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"page": 0}, "page must be at least 1"),
        (
            {"per_page": 101},
            "per_page must be between 1 and 100",
        ),
        ({"query": "   "}, "query cannot be blank"),
        ({"year": "   "}, "year cannot be blank"),
        (
            {"series_types": ("Unknown",)},
            "Unsupported MangaUpdates series type",
        ),
        (
            {"filters": ("unknown",)},
            "Unsupported MangaUpdates filter",
        ),
        (
            {"order_by": "unknown"},
            "Unsupported MangaUpdates order field",
        ),
    ],
)
@pytest.mark.asyncio
async def test_discovery_arguments_are_validated_before_io(
    arguments: dict[str, object],
    message: str,
) -> None:
    requests: list[httpx2.Request] = []

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            {},
            requests=requests,
        ),
    ) as client:
        with pytest.raises(ValueError, match=message):
            await client.discover_series_page(
                **arguments  # type: ignore[arg-type]
            )

    assert requests == []


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
async def test_get_cover_image_validates_and_returns_detected_format(
) -> None:
    requests: list[httpx2.Request] = []

    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(
            200,
            content=b"\x89PNG\r\n\x1a\nimage-data",
            headers={"Content-Type": "application/octet-stream"},
        )

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        user_agent="MangaRecon-Test/1.0",
        transport=httpx2.MockTransport(handler),
    ) as client:
        result = await client.get_cover_image(
            " https://cdn.mangaupdates.com/image/i42.png "
        )

    assert result.content == b"\x89PNG\r\n\x1a\nimage-data"
    assert result.content_type == "image/png"
    assert result.extension == "png"
    assert len(requests) == 1
    assert requests[0].url.host == "cdn.mangaupdates.com"
    assert requests[0].url.path == "/image/i42.png"
    assert requests[0].headers["Accept"].startswith("image/webp")
    assert requests[0].headers["User-Agent"] == (
        "MangaRecon-Test/1.0"
    )


@pytest.mark.parametrize(
    ("content", "content_type", "extension"),
    [
        (b"\xff\xd8\xffjpeg", "image/jpeg", "jpg"),
        (b"GIF87a-data", "image/gif", "gif"),
        (b"GIF89a-data", "image/gif", "gif"),
        (b"RIFF\x04\x00\x00\x00WEBPdata", "image/webp", "webp"),
    ],
)
@pytest.mark.asyncio
async def test_get_cover_image_supports_expected_image_formats(
    content: bytes,
    content_type: str,
    extension: str,
) -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(200, content=content)

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=httpx2.MockTransport(handler),
    ) as client:
        result = await client.get_cover_image(
            "https://cdn.mangaupdates.com/image/cover"
        )

    assert result.content_type == content_type
    assert result.extension == extension


@pytest.mark.parametrize(
    "source_url",
    [
        "http://cdn.mangaupdates.com/image/i42.png",
        "https://example.com/image/i42.png",
        "https://user@cdn.mangaupdates.com/image/i42.png",
        "https://cdn.mangaupdates.com/not-image/i42.png",
        "https://cdn.mangaupdates.com:invalid/image/i42.png",
        "   ",
    ],
)
@pytest.mark.asyncio
async def test_get_cover_image_rejects_unapproved_urls_before_io(
    source_url: str,
) -> None:
    requests: list[httpx2.Request] = []

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=make_json_transport(
            {},
            requests=requests,
        ),
    ) as client:
        with pytest.raises(MangaUpdatesInvalidCoverError):
            await client.get_cover_image(source_url)

    assert requests == []


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty cover image"),
        (b"not-an-image", "not a supported image"),
    ],
)
@pytest.mark.asyncio
async def test_get_cover_image_rejects_invalid_content(
    content: bytes,
    message: str,
) -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(200, content=content)

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=httpx2.MockTransport(handler),
    ) as client:
        with pytest.raises(
            MangaUpdatesInvalidCoverError,
            match=message,
        ):
            await client.get_cover_image(
                "https://cdn.mangaupdates.com/image/i42.png"
            )


@pytest.mark.asyncio
async def test_get_cover_image_enforces_size_limit() -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"\x89PNG\r\n\x1a\n",
        )

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        max_cover_bytes=7,
        transport=httpx2.MockTransport(handler),
    ) as client:
        with pytest.raises(
            MangaUpdatesInvalidCoverError,
            match="size limit",
        ):
            await client.get_cover_image(
                "https://cdn.mangaupdates.com/image/i42.png"
            )


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (404, MangaUpdatesHTTPError),
        (429, MangaUpdatesRateLimitError),
        (503, MangaUpdatesUnavailableError),
    ],
)
@pytest.mark.asyncio
async def test_get_cover_image_classifies_http_failures(
    status_code: int,
    expected_exception: type[Exception],
) -> None:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            status_code,
            headers={"Retry-After": "30"},
        )

    async with MangaUpdatesClient(
        min_request_interval_seconds=0,
        transport=httpx2.MockTransport(handler),
    ) as client:
        with pytest.raises(expected_exception):
            await client.get_cover_image(
                "https://cdn.mangaupdates.com/image/i42.png"
            )


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
