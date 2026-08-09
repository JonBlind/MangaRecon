from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.clients.mangaupdates_client import (
    MANGAUPDATES_SERIES_FILTERS,
    MANGAUPDATES_SERIES_ORDER_FIELDS,
    MANGAUPDATES_SERIES_TYPES,
    MangaUpdatesClient,
)


DISCOVERY_SCHEMA_VERSION = 1
MAX_DISCOVERY_RESULTS = 10_000

DiscoveryStatus = Literal[
    "in_progress",
    "failed",
    "complete",
]


class MangaUpdatesDiscoveryError(ValueError):
    """
    Base exception for invalid discovery data or state.
    """


class MangaUpdatesDiscoveryResponseError(
    MangaUpdatesDiscoveryError
):
    """
    Raised when a discovery page cannot be interpreted safely.
    """


class MangaUpdatesDiscoveryRunError(RuntimeError):
    """
    Raised after a failed page has been recorded in the checkpoint.
    """


def _normalize_optional_text(
    value: str | None,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise MangaUpdatesDiscoveryError(
            f"{field_name} must be a string or null."
        )

    normalized = value.strip()

    if not normalized:
        raise MangaUpdatesDiscoveryError(
            f"{field_name} cannot be blank."
        )

    return normalized


def _normalize_text_values(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    normalized: list[str] = []

    for value in values:
        item = _normalize_optional_text(
            value,
            field_name=field_name,
        )

        if item not in normalized:
            normalized.append(item)

    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class MangaUpdatesDiscoveryRequest:
    """
    Stable filter partition and limits for one discovery manifest.
    """

    limit: int = 100
    per_page: int = 100
    query: str | None = None
    series_types: tuple[str, ...] = ()
    year: str | None = None
    genres: tuple[str, ...] = ()
    exclude_genres: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    order_by: str = "rating"

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(
            self.limit,
            int,
        ):
            raise MangaUpdatesDiscoveryError(
                "limit must be an integer."
            )

        if not 1 <= self.limit <= MAX_DISCOVERY_RESULTS:
            raise MangaUpdatesDiscoveryError(
                (
                    "limit must be between 1 and "
                    f"{MAX_DISCOVERY_RESULTS}."
                )
            )

        if isinstance(self.per_page, bool) or not isinstance(
            self.per_page,
            int,
        ):
            raise MangaUpdatesDiscoveryError(
                "per_page must be an integer."
            )

        if not 1 <= self.per_page <= 100:
            raise MangaUpdatesDiscoveryError(
                "per_page must be between 1 and 100."
            )

        object.__setattr__(
            self,
            "query",
            _normalize_optional_text(
                self.query,
                field_name="query",
            ),
        )
        object.__setattr__(
            self,
            "year",
            _normalize_optional_text(
                self.year,
                field_name="year",
            ),
        )

        for field_name in (
            "series_types",
            "genres",
            "exclude_genres",
            "filters",
        ):
            values = getattr(self, field_name)

            if not isinstance(values, tuple):
                raise MangaUpdatesDiscoveryError(
                    f"{field_name} must be a tuple."
                )

            object.__setattr__(
                self,
                field_name,
                _normalize_text_values(
                    values,
                    field_name=field_name,
                ),
            )

        unsupported_types = set(self.series_types).difference(
            MANGAUPDATES_SERIES_TYPES
        )

        if unsupported_types:
            raise MangaUpdatesDiscoveryError(
                (
                    "Unsupported MangaUpdates series type: "
                    f"{sorted(unsupported_types)[0]}."
                )
            )

        unsupported_filters = set(self.filters).difference(
            MANGAUPDATES_SERIES_FILTERS
        )

        if unsupported_filters:
            raise MangaUpdatesDiscoveryError(
                (
                    "Unsupported MangaUpdates filter: "
                    f"{sorted(unsupported_filters)[0]}."
                )
            )

        if self.order_by not in MANGAUPDATES_SERIES_ORDER_FIELDS:
            raise MangaUpdatesDiscoveryError(
                (
                    "Unsupported MangaUpdates order field: "
                    f"{self.order_by}."
                )
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit": self.limit,
            "per_page": self.per_page,
            "query": self.query,
            "series_types": list(self.series_types),
            "year": self.year,
            "genres": list(self.genres),
            "exclude_genres": list(
                self.exclude_genres
            ),
            "filters": list(self.filters),
            "order_by": self.order_by,
        }

    @classmethod
    def from_dict(
        cls,
        payload: object,
    ) -> MangaUpdatesDiscoveryRequest:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryError(
                "request must be an object."
            )

        def text_tuple(field_name: str) -> tuple[str, ...]:
            value = payload.get(field_name, [])

            if not isinstance(value, list) or any(
                not isinstance(item, str) for item in value
            ):
                raise MangaUpdatesDiscoveryError(
                    f"request.{field_name} must be a string array."
                )

            return tuple(value)

        return cls(
            limit=payload.get("limit", 100),
            per_page=payload.get("per_page", 100),
            query=payload.get("query"),
            series_types=text_tuple("series_types"),
            year=payload.get("year"),
            genres=text_tuple("genres"),
            exclude_genres=text_tuple("exclude_genres"),
            filters=text_tuple("filters"),
            order_by=payload.get("order_by", "rating"),
        )


def _required_positive_int(
    value: object,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
    ):
        raise MangaUpdatesDiscoveryResponseError(
            f"{field_name} must be a positive integer."
        )

    return value


def _required_nonnegative_int(
    value: object,
    *,
    field_name: str,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise MangaUpdatesDiscoveryResponseError(
            f"{field_name} must be a nonnegative integer."
        )

    return value


def _optional_response_text(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise MangaUpdatesDiscoveryResponseError(
            f"{field_name} must be a string or null."
        )

    normalized = value.strip()
    return normalized or None


@dataclass(frozen=True, slots=True)
class MangaUpdatesDiscoveredSeries:
    series_id: int
    title: str
    media_type: str | None
    year: str | None
    source_url: str | None
    source_updated_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "title": self.title,
            "type": self.media_type,
            "year": self.year,
            "source_url": self.source_url,
            "source_updated_at": self.source_updated_at,
        }

    @classmethod
    def from_search_result(
        cls,
        payload: object,
    ) -> MangaUpdatesDiscoveredSeries:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryResponseError(
                "result must be an object."
            )

        record = payload.get("record")

        if not isinstance(record, dict):
            raise MangaUpdatesDiscoveryResponseError(
                "result.record must be an object."
            )

        series_id = _required_positive_int(
            record.get("series_id"),
            field_name="result.record.series_id",
        )
        title = _optional_response_text(
            record.get("title"),
            field_name="result.record.title",
        )

        if title is None:
            raise MangaUpdatesDiscoveryResponseError(
                "result.record.title cannot be blank."
            )

        last_updated = record.get("last_updated")

        if last_updated is None:
            source_updated_at = None
        elif isinstance(last_updated, dict):
            source_updated_at = _optional_response_text(
                last_updated.get("as_rfc3339"),
                field_name=(
                    "result.record.last_updated.as_rfc3339"
                ),
            )
        else:
            raise MangaUpdatesDiscoveryResponseError(
                "result.record.last_updated must be an object or null."
            )

        return cls(
            series_id=series_id,
            title=title,
            media_type=_optional_response_text(
                record.get("type"),
                field_name="result.record.type",
            ),
            year=_optional_response_text(
                record.get("year"),
                field_name="result.record.year",
            ),
            source_url=_optional_response_text(
                record.get("url"),
                field_name="result.record.url",
            ),
            source_updated_at=source_updated_at,
        )

    @classmethod
    def from_dict(
        cls,
        payload: object,
    ) -> MangaUpdatesDiscoveredSeries:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryError(
                "series entry must be an object."
            )

        try:
            return cls.from_search_result(
                {
                    "record": {
                        "series_id": payload.get("series_id"),
                        "title": payload.get("title"),
                        "type": payload.get("type"),
                        "year": payload.get("year"),
                        "url": payload.get("source_url"),
                        "last_updated": (
                            {
                                "as_rfc3339": payload.get(
                                    "source_updated_at"
                                )
                            }
                            if payload.get("source_updated_at")
                            is not None
                            else None
                        ),
                    }
                }
            )
        except MangaUpdatesDiscoveryResponseError as exc:
            raise MangaUpdatesDiscoveryError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class MangaUpdatesDiscoveryIssue:
    page: int
    result_index: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "result_index": self.result_index,
            "message": self.message,
        }

    @classmethod
    def from_dict(
        cls,
        payload: object,
    ) -> MangaUpdatesDiscoveryIssue:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryError(
                "issue entry must be an object."
            )

        page = payload.get("page")
        result_index = payload.get("result_index")
        message = payload.get("message")

        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
        ):
            raise MangaUpdatesDiscoveryError(
                "issue.page must be a positive integer."
            )

        if (
            isinstance(result_index, bool)
            or not isinstance(result_index, int)
            or result_index < 0
        ):
            raise MangaUpdatesDiscoveryError(
                "issue.result_index must be nonnegative."
            )

        if not isinstance(message, str) or not message.strip():
            raise MangaUpdatesDiscoveryError(
                "issue.message must be a nonblank string."
            )

        return cls(
            page=page,
            result_index=result_index,
            message=message.strip(),
        )


@dataclass(frozen=True, slots=True)
class MangaUpdatesDiscoveryPage:
    total_hits: int
    page: int
    per_page: int
    raw_result_count: int
    series: tuple[MangaUpdatesDiscoveredSeries, ...]
    issues: tuple[MangaUpdatesDiscoveryIssue, ...]

    @property
    def has_more(self) -> bool:
        return (
            self.raw_result_count > 0
            and self.page * self.per_page < self.total_hits
        )

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        expected_page: int,
    ) -> MangaUpdatesDiscoveryPage:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryResponseError(
                "Discovery response must be an object."
            )

        upstream_status = payload.get("status")

        if isinstance(upstream_status, str):
            upstream_reason = payload.get("reason")
            reason = (
                upstream_reason.strip()
                if isinstance(upstream_reason, str)
                and upstream_reason.strip()
                else upstream_status.strip()
            )
            raise MangaUpdatesDiscoveryResponseError(
                f"MangaUpdates discovery error: {reason}"
            )

        total_hits = _required_nonnegative_int(
            payload.get("total_hits"),
            field_name="total_hits",
        )
        page = _required_positive_int(
            payload.get("page"),
            field_name="page",
        )
        per_page = _required_positive_int(
            payload.get("per_page"),
            field_name="per_page",
        )

        if page != expected_page:
            raise MangaUpdatesDiscoveryResponseError(
                (
                    f"Expected page {expected_page}, but "
                    f"MangaUpdates returned page {page}."
                )
            )

        if per_page > 100:
            raise MangaUpdatesDiscoveryResponseError(
                "per_page cannot exceed 100."
            )

        raw_results = payload.get("results")

        if not isinstance(raw_results, list):
            raise MangaUpdatesDiscoveryResponseError(
                "results must be an array."
            )

        series: list[MangaUpdatesDiscoveredSeries] = []
        issues: list[MangaUpdatesDiscoveryIssue] = []

        for index, raw_result in enumerate(raw_results):
            try:
                discovered = (
                    MangaUpdatesDiscoveredSeries.from_search_result(
                        raw_result
                    )
                )
            except MangaUpdatesDiscoveryResponseError as exc:
                issues.append(
                    MangaUpdatesDiscoveryIssue(
                        page=page,
                        result_index=index,
                        message=str(exc),
                    )
                )
            else:
                series.append(discovered)

        return cls(
            total_hits=total_hits,
            page=page,
            per_page=per_page,
            raw_result_count=len(raw_results),
            series=tuple(series),
            issues=tuple(issues),
        )


@dataclass(slots=True)
class MangaUpdatesDiscoveryState:
    request: MangaUpdatesDiscoveryRequest
    status: DiscoveryStatus = "in_progress"
    next_page: int | None = 1
    pages_completed: int = 0
    reported_total_hits: int | None = None
    series: list[MangaUpdatesDiscoveredSeries] = field(
        default_factory=list
    )
    issues: list[MangaUpdatesDiscoveryIssue] = field(
        default_factory=list
    )
    last_error: str | None = None

    def add_page(
        self,
        page: MangaUpdatesDiscoveryPage,
    ) -> None:
        if self.next_page is None:
            raise MangaUpdatesDiscoveryError(
                "A complete discovery cannot accept another page."
            )

        if page.page != self.next_page:
            raise MangaUpdatesDiscoveryError(
                (
                    f"Expected state page {self.next_page}, "
                    f"received page {page.page}."
                )
            )

        existing_ids = {
            item.series_id for item in self.series
        }

        for discovered in page.series:
            if len(self.series) >= self.request.limit:
                break

            if discovered.series_id in existing_ids:
                continue

            self.series.append(discovered)
            existing_ids.add(discovered.series_id)

        self.issues.extend(page.issues)
        self.pages_completed += 1
        self.reported_total_hits = page.total_hits
        self.last_error = None

        if (
            len(self.series) >= self.request.limit
            or not page.has_more
        ):
            self.status = "complete"
            self.next_page = None
        else:
            self.status = "in_progress"
            self.next_page = page.page + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DISCOVERY_SCHEMA_VERSION,
            "provider": "mangaupdates",
            "status": self.status,
            "request": self.request.to_dict(),
            "next_page": self.next_page,
            "pages_completed": self.pages_completed,
            "reported_total_hits": self.reported_total_hits,
            "series_count": len(self.series),
            "series": [item.to_dict() for item in self.series],
            "issues": [issue.to_dict() for issue in self.issues],
            "last_error": self.last_error,
        }

    @classmethod
    def from_dict(
        cls,
        payload: object,
    ) -> MangaUpdatesDiscoveryState:
        if not isinstance(payload, dict):
            raise MangaUpdatesDiscoveryError(
                "Discovery manifest must be an object."
            )

        if payload.get("schema_version") != (
            DISCOVERY_SCHEMA_VERSION
        ):
            raise MangaUpdatesDiscoveryError(
                "Unsupported discovery manifest schema version."
            )

        if payload.get("provider") != "mangaupdates":
            raise MangaUpdatesDiscoveryError(
                "Discovery manifest provider must be mangaupdates."
            )

        status = payload.get("status")

        if status not in {
            "in_progress",
            "failed",
            "complete",
        }:
            raise MangaUpdatesDiscoveryError(
                "Discovery manifest has an invalid status."
            )

        next_page = payload.get("next_page")

        if next_page is not None and (
            isinstance(next_page, bool)
            or not isinstance(next_page, int)
            or next_page < 1
        ):
            raise MangaUpdatesDiscoveryError(
                "next_page must be a positive integer or null."
            )

        if status == "complete" and next_page is not None:
            raise MangaUpdatesDiscoveryError(
                "A complete manifest must have next_page set to null."
            )

        if status != "complete" and next_page is None:
            raise MangaUpdatesDiscoveryError(
                "An incomplete manifest must have a next_page."
            )

        pages_completed = payload.get("pages_completed")

        if (
            isinstance(pages_completed, bool)
            or not isinstance(pages_completed, int)
            or pages_completed < 0
        ):
            raise MangaUpdatesDiscoveryError(
                "pages_completed must be nonnegative."
            )

        reported_total_hits = payload.get(
            "reported_total_hits"
        )

        if reported_total_hits is not None and (
            isinstance(reported_total_hits, bool)
            or not isinstance(reported_total_hits, int)
            or reported_total_hits < 0
        ):
            raise MangaUpdatesDiscoveryError(
                (
                    "reported_total_hits must be a "
                    "nonnegative integer or null."
                )
            )

        raw_series = payload.get("series")
        raw_issues = payload.get("issues")

        if not isinstance(raw_series, list):
            raise MangaUpdatesDiscoveryError(
                "series must be an array."
            )

        if not isinstance(raw_issues, list):
            raise MangaUpdatesDiscoveryError(
                "issues must be an array."
            )

        request = MangaUpdatesDiscoveryRequest.from_dict(
            payload.get("request")
        )
        series = [
            MangaUpdatesDiscoveredSeries.from_dict(item)
            for item in raw_series
        ]

        if len(series) != len(
            {item.series_id for item in series}
        ):
            raise MangaUpdatesDiscoveryError(
                "series contains duplicate IDs."
            )

        if len(series) > request.limit:
            raise MangaUpdatesDiscoveryError(
                "series_count exceeds the request limit."
            )

        if payload.get("series_count") != len(series):
            raise MangaUpdatesDiscoveryError(
                "series_count does not match series."
            )

        last_error = payload.get("last_error")

        if last_error is not None and (
            not isinstance(last_error, str)
            or not last_error.strip()
        ):
            raise MangaUpdatesDiscoveryError(
                "last_error must be a nonblank string or null."
            )

        return cls(
            request=request,
            status=status,
            next_page=next_page,
            pages_completed=pages_completed,
            reported_total_hits=reported_total_hits,
            series=series,
            issues=[
                MangaUpdatesDiscoveryIssue.from_dict(item)
                for item in raw_issues
            ],
            last_error=last_error,
        )


CheckpointCallback = Callable[
    [MangaUpdatesDiscoveryState],
    None,
]


def _client_options(
    request: MangaUpdatesDiscoveryRequest,
    *,
    page: int,
) -> dict[str, Any]:
    return {
        "query": request.query,
        "page": page,
        "per_page": request.per_page,
        "series_types": request.series_types,
        "year": request.year,
        "genres": request.genres,
        "exclude_genres": request.exclude_genres,
        "filters": request.filters,
        "order_by": request.order_by,
    }


async def discover_mangaupdates_catalog(
    client: MangaUpdatesClient,
    *,
    state: MangaUpdatesDiscoveryState,
    checkpoint: CheckpointCallback | None = None,
) -> MangaUpdatesDiscoveryState:
    """
    Resume discovery until its limit or source partition is exhausted.

    A checkpoint is emitted after every successful page and after a
    recoverable page failure. Cancellation and keyboard interruption are
    deliberately not swallowed; the most recent successful page remains
    resumable.
    """
    if state.status == "complete":
        return state

    state.status = "in_progress"
    state.last_error = None

    while state.status != "complete":
        if state.next_page is None:
            raise MangaUpdatesDiscoveryError(
                "Incomplete discovery state has no next page."
            )

        requested_page = state.next_page

        try:
            payload = await client.discover_series_page(
                **_client_options(
                    state.request,
                    page=requested_page,
                )
            )
            page = MangaUpdatesDiscoveryPage.from_payload(
                payload,
                expected_page=requested_page,
            )
        except Exception as exc:
            message = str(exc).strip() or type(exc).__name__
            state.status = "failed"
            state.last_error = message

            if checkpoint is not None:
                checkpoint(state)

            raise MangaUpdatesDiscoveryRunError(
                message
            ) from exc

        state.add_page(page)

        if checkpoint is not None:
            checkpoint(state)

    return state
