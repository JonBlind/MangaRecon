from __future__ import annotations

from asyncio import Lock, sleep
from collections.abc import Sequence
from time import monotonic
from typing import Any, Self
from urllib.parse import urlsplit

import httpx2

from backend.config.settings import settings
from backend.ingestion.images import DownloadedCoverImage


MANGAUPDATES_SERIES_TYPES = (
    "Artbook",
    "Doujinshi",
    "Drama CD",
    "Filipino",
    "Indonesian",
    "Manga",
    "Manhwa",
    "Manhua",
    "Novel",
    "OEL",
    "Thai",
    "Vietnamese",
    "Malaysian",
    "Nordic",
    "French",
    "Spanish",
    "German",
)

MANGAUPDATES_SERIES_FILTERS = (
    "scanlated",
    "completed",
    "oneshots",
    "no_oneshots",
    "some_releases",
    "no_releases",
)

MANGAUPDATES_SERIES_ORDER_FIELDS = (
    "score",
    "title",
    "rank",
    "rating",
    "year",
    "date_added",
    "week_pos",
    "month1_pos",
    "month3_pos",
    "month6_pos",
    "year_pos",
    "list_reading",
    "list_wish",
    "list_complete",
    "list_unfinished",
)

_MANGAUPDATES_COVER_HOST = "cdn.mangaupdates.com"
_DEFAULT_MAX_COVER_BYTES = 5 * 1024 * 1024


class MangaUpdatesClientError(RuntimeError):
    """
    Base exception for MangaUpdates client failures.
    """


class MangaUpdatesTransportError(MangaUpdatesClientError):
    """
    Raised when MangaUpdates cannot be reached.
    """


class MangaUpdatesHTTPError(MangaUpdatesClientError):
    """
    Raised when MangaUpdates returns an unsuccessful HTTP status.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class MangaUpdatesRateLimitError(MangaUpdatesHTTPError):
    """
    Raised when MangaUpdates returns HTTP 429.
    """

    def __init__(
        self,
        *,
        retry_after: str | None,
    ) -> None:
        super().__init__(
            "MangaUpdates rate limit exceeded.",
            status_code=429,
        )
        self.retry_after = retry_after


class MangaUpdatesUnavailableError(MangaUpdatesHTTPError):
    """
    Raised when MangaUpdates returns a server error.
    """


class MangaUpdatesInvalidResponseError(
    MangaUpdatesClientError
):
    """
    Raised when MangaUpdates returns an invalid response body.
    """


class MangaUpdatesInvalidCoverError(
    MangaUpdatesClientError
):
    """Raised when a MangaUpdates cover is unsafe or not an image."""


class MangaUpdatesClient:
    """
    Asynchronous client for public MangaUpdates series endpoints.

    One client instance should be reused for an entire ingestion job so
    connection pooling and request spacing work correctly.
    """

    def __init__(
        self,
        *,
        base_url: str = (
            "https://api.mangaupdates.com/v1"
        ),
        timeout_seconds: float = 10.0,
        min_request_interval_seconds: float = 1.0,
        user_agent: str = "MangaRecon/0.1",
        max_cover_bytes: int = _DEFAULT_MAX_COVER_BYTES,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        normalized_base_url = base_url.strip()
        normalized_user_agent = user_agent.strip()

        if not normalized_base_url:
            raise ValueError("base_url cannot be blank.")

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if min_request_interval_seconds < 0:
            raise ValueError(
                "min_request_interval_seconds cannot be negative."
            )

        if not normalized_user_agent:
            raise ValueError("user_agent cannot be blank.")

        if max_cover_bytes < 1:
            raise ValueError(
                "max_cover_bytes must be greater than zero."
            )

        self._min_request_interval_seconds = (
            min_request_interval_seconds
        )
        self._max_cover_bytes = max_cover_bytes
        self._request_lock = Lock()
        self._last_request_started_at: float | None = None

        self._http_client = httpx2.AsyncClient(
            base_url=(
                f"{normalized_base_url.rstrip('/')}/"
            ),
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": normalized_user_agent,
            },
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """
        Close the underlying HTTP connection pool.
        """
        await self._http_client.aclose()

    async def search_series(
        self,
        query: str,
        *,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """
        Search MangaUpdates for series matching a title.
        """
        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError("query cannot be blank.")

        if page < 1:
            raise ValueError("page must be at least 1.")

        if per_page < 1:
            raise ValueError("per_page must be at least 1.")

        return await self._request(
            "POST",
            "series/search",
            json_body={
                "search": normalized_query,
                "page": page,
                "perpage": per_page,
            },
        )

    async def discover_series_page(
        self,
        *,
        query: str | None = None,
        page: int = 1,
        per_page: int = 100,
        series_types: Sequence[str] = (),
        year: str | None = None,
        genres: Sequence[str] = (),
        exclude_genres: Sequence[str] = (),
        filters: Sequence[str] = (),
        order_by: str = "rating",
    ) -> dict[str, Any]:
        """
        Retrieve one filtered page for controlled catalog discovery.

        Unlike title search, MangaUpdates permits this request without a
        search string when structured filters are supplied.
        """
        if page < 1:
            raise ValueError("page must be at least 1.")

        if not 1 <= per_page <= 100:
            raise ValueError(
                "per_page must be between 1 and 100."
            )

        normalized_query = self._optional_text(
            query,
            field_name="query",
        )
        normalized_year = self._optional_text(
            year,
            field_name="year",
        )
        normalized_types = self._text_values(
            series_types,
            field_name="series_types",
        )
        normalized_genres = self._text_values(
            genres,
            field_name="genres",
        )
        normalized_excluded_genres = self._text_values(
            exclude_genres,
            field_name="exclude_genres",
        )
        normalized_filters = self._text_values(
            filters,
            field_name="filters",
        )

        unsupported_types = set(
            normalized_types
        ).difference(MANGAUPDATES_SERIES_TYPES)

        if unsupported_types:
            raise ValueError(
                (
                    "Unsupported MangaUpdates series type: "
                    f"{sorted(unsupported_types)[0]}."
                )
            )

        unsupported_filters = set(
            normalized_filters
        ).difference(MANGAUPDATES_SERIES_FILTERS)

        if unsupported_filters:
            raise ValueError(
                (
                    "Unsupported MangaUpdates filter: "
                    f"{sorted(unsupported_filters)[0]}."
                )
            )

        if order_by not in MANGAUPDATES_SERIES_ORDER_FIELDS:
            raise ValueError(
                (
                    "Unsupported MangaUpdates order field: "
                    f"{order_by}."
                )
            )

        request_body: dict[str, Any] = {
            "page": page,
            "perpage": per_page,
            "orderby": order_by,
        }

        optional_values: tuple[
            tuple[str, str | tuple[str, ...] | None],
            ...,
        ] = (
            ("search", normalized_query),
            ("type", normalized_types or None),
            ("year", normalized_year),
            ("genre", normalized_genres or None),
            (
                "exclude_genre",
                normalized_excluded_genres or None,
            ),
            ("filters", normalized_filters or None),
        )

        for key, value in optional_values:
            if value is not None:
                request_body[key] = value

        return await self._request(
            "POST",
            "series/search",
            json_body=request_body,
        )

    async def get_series(
        self,
        series_id: int,
        *,
        unrendered_fields: bool = False,
    ) -> dict[str, Any]:
        """
        Retrieve the full MangaUpdates record for one series.
        """
        if series_id < 1:
            raise ValueError(
                "series_id must be greater than zero."
            )

        params = None

        if unrendered_fields:
            params = {
                "unrenderedFields": "true",
            }

        return await self._request(
            "GET",
            f"series/{series_id}",
            params=params,
        )

    async def get_cover_image(
        self,
        source_url: str,
    ) -> DownloadedCoverImage:
        """Download and validate one MangaUpdates-hosted cover image."""
        normalized_url = self._validated_cover_url(source_url)
        await self._wait_for_request_slot()

        try:
            async with self._http_client.stream(
                "GET",
                normalized_url,
                headers={
                    "Accept": "image/webp,image/png,image/jpeg,image/gif",
                },
            ) as response:
                self._validate_cover_response_status(response)
                content = await self._read_cover_content(response)
        except httpx2.RequestError as exc:
            raise MangaUpdatesTransportError(
                "Could not reach MangaUpdates for a cover image."
            ) from exc

        content_type, extension = self._detect_cover_format(content)

        return DownloadedCoverImage(
            content=content,
            content_type=content_type,
            extension=extension,
        )

    @staticmethod
    def _validate_cover_response_status(
        response: httpx2.Response,
    ) -> None:
        if response.status_code == 429:
            raise MangaUpdatesRateLimitError(
                retry_after=response.headers.get("Retry-After"),
            )

        if response.status_code >= 500:
            raise MangaUpdatesUnavailableError(
                (
                    "MangaUpdates returned server error "
                    f"{response.status_code} for a cover image."
                ),
                status_code=response.status_code,
            )

        if not 200 <= response.status_code < 300:
            raise MangaUpdatesHTTPError(
                (
                    "MangaUpdates returned HTTP "
                    f"{response.status_code} for a cover image."
                ),
                status_code=response.status_code,
            )

    async def _read_cover_content(
        self,
        response: httpx2.Response,
    ) -> bytes:
        declared_length = response.headers.get("Content-Length")

        if declared_length is not None:
            try:
                parsed_length = int(declared_length)
            except ValueError:
                parsed_length = None

            if (
                parsed_length is not None
                and parsed_length > self._max_cover_bytes
            ):
                raise MangaUpdatesInvalidCoverError(
                    "MangaUpdates cover image exceeds the configured size limit."
                )

        chunks: list[bytes] = []
        content_length = 0

        async for chunk in response.aiter_bytes():
            content_length += len(chunk)

            if content_length > self._max_cover_bytes:
                raise MangaUpdatesInvalidCoverError(
                    "MangaUpdates cover image exceeds the configured size limit."
                )

            chunks.append(chunk)

        content = b"".join(chunks)

        if not content:
            raise MangaUpdatesInvalidCoverError(
                "MangaUpdates returned an empty cover image."
            )

        return content

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self._wait_for_request_slot()

        try:
            response = await self._http_client.request(
                method,
                path,
                json=json_body,
                params=params,
            )
        except httpx2.RequestError as exc:
            raise MangaUpdatesTransportError(
                "Could not reach MangaUpdates."
            ) from exc

        if response.status_code == 429:
            raise MangaUpdatesRateLimitError(
                retry_after=response.headers.get(
                    "Retry-After"
                ),
            )

        if response.status_code >= 500:
            raise MangaUpdatesUnavailableError(
                (
                    "MangaUpdates returned server error "
                    f"{response.status_code}."
                ),
                status_code=response.status_code,
            )

        if not 200 <= response.status_code < 300:
            raise MangaUpdatesHTTPError(
                (
                    "MangaUpdates returned HTTP "
                    f"{response.status_code}."
                ),
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise MangaUpdatesInvalidResponseError(
                "MangaUpdates returned invalid JSON."
            ) from exc

        if not isinstance(payload, dict):
            raise MangaUpdatesInvalidResponseError(
                (
                    "MangaUpdates returned JSON that was "
                    "not an object."
                )
            )

        return payload

    @staticmethod
    def _validated_cover_url(value: str) -> str:
        if not isinstance(value, str):
            raise MangaUpdatesInvalidCoverError(
                "MangaUpdates cover URL must be a string."
            )

        normalized = value.strip()

        try:
            parsed = urlsplit(normalized)
            port = parsed.port
        except ValueError as exc:
            raise MangaUpdatesInvalidCoverError(
                "MangaUpdates cover URL is invalid."
            ) from exc

        if (
            parsed.scheme != "https"
            or parsed.hostname != _MANGAUPDATES_COVER_HOST
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.path.startswith("/image/")
        ):
            raise MangaUpdatesInvalidCoverError(
                "MangaUpdates cover URL is not an approved CDN URL."
            )

        return normalized

    @staticmethod
    def _detect_cover_format(content: bytes) -> tuple[str, str]:
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png", "png"

        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg", "jpg"

        if content.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif", "gif"

        if (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ):
            return "image/webp", "webp"

        raise MangaUpdatesInvalidCoverError(
            "MangaUpdates cover response is not a supported image."
        )

    @staticmethod
    def _optional_text(
        value: str | None,
        *,
        field_name: str,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string or null."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} cannot be blank.")

        return normalized

    @classmethod
    def _text_values(
        cls,
        values: Sequence[str],
        *,
        field_name: str,
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for value in values:
            item = cls._optional_text(
                value,
                field_name=field_name,
            )

            if item not in normalized:
                normalized.append(item)

        return tuple(normalized)

    async def _wait_for_request_slot(self) -> None:
        async with self._request_lock:
            now = monotonic()

            if self._last_request_started_at is not None:
                elapsed = (
                    now - self._last_request_started_at
                )
                remaining = (
                    self._min_request_interval_seconds
                    - elapsed
                )

                if remaining > 0:
                    await sleep(remaining)
                    now = monotonic()

            self._last_request_started_at = now


def create_mangaupdates_client(
    *,
    min_request_interval_seconds: float | None = None,
) -> MangaUpdatesClient:
    """
    Create a MangaUpdates client from application settings.

    The optional interval override is intended for controlled CLI jobs.
    """
    request_interval = (
        settings.mangaupdates_min_request_interval_seconds
        if min_request_interval_seconds is None
        else min_request_interval_seconds
    )

    return MangaUpdatesClient(
        base_url=settings.mangaupdates_base_url,
        timeout_seconds=(
            settings.mangaupdates_timeout_seconds
        ),
        min_request_interval_seconds=request_interval,
        user_agent=settings.mangaupdates_user_agent,
    )
