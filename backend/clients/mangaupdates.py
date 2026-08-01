from __future__ import annotations

from asyncio import Lock, sleep
from time import monotonic
from typing import Any, Self

import httpx2


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
    Raised when MangaUpdates returns invalid JSON.
    """


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
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if min_request_interval_seconds < 0:
            raise ValueError(
                "min_request_interval_seconds cannot be negative."
            )

        self._min_request_interval_seconds = (
            min_request_interval_seconds
        )
        self._request_lock = Lock()
        self._last_request_started_at: float | None = None

        self._http_client = httpx2.AsyncClient(
            base_url=f"{base_url.rstrip('/')}/",
            timeout=timeout_seconds,
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
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
    ) -> Any:
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

    async def get_series(
        self,
        series_id: int,
        *,
        unrendered_fields: bool = False,
    ) -> Any:
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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
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
            return response.json()
        except ValueError as exc:
            raise MangaUpdatesInvalidResponseError(
                "MangaUpdates returned invalid JSON."
            ) from exc

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