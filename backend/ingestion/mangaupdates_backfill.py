from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from backend.clients.mangaupdates_client import (
    MANGAUPDATES_SERIES_TYPES,
)
from backend.ingestion.mangaupdates_discovery import (
    MangaUpdatesDiscoveryPage,
)


CATALOG_BACKFILL_SCHEMA_VERSION = 1
MANGAUPDATES_SEARCH_RESULT_CAP = 10_000
DEFAULT_MINIMUM_PUBLICATION_YEAR = 1900


class MangaUpdatesBackfillError(ValueError):
    """Raised when a historical checkpoint cannot advance safely."""


class MangaUpdatesBackfillPartitionLimitError(
    MangaUpdatesBackfillError
):
    """Raised when even a year-and-type partition reaches the API cap."""


def _positive_series_ids(
    values: object,
    *,
    field_name: str = "pending_series_ids",
) -> tuple[int, ...]:
    if not isinstance(values, list):
        raise MangaUpdatesBackfillError(
            f"{field_name} must be an array."
        )

    normalized: list[int] = []
    seen: set[int] = set()

    for value in values:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 1
        ):
            raise MangaUpdatesBackfillError(
                f"{field_name} must contain positive integers."
            )

        if value not in seen:
            normalized.append(value)
            seen.add(value)

    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class MangaUpdatesBackfillCheckpoint:
    """Persistent cursor and separate deferred discovery queues."""

    start_year: int
    current_year: int
    minimum_year: int = DEFAULT_MINIMUM_PUBLICATION_YEAR
    page: int = 1
    split_by_type: bool = False
    series_type_index: int = 0
    pending_series_ids: tuple[int, ...] = ()
    pending_recent_series_ids: tuple[int, ...] = ()
    excluded_recent_series_ids: tuple[int, ...] = ()
    complete: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "start_year",
            "current_year",
            "minimum_year",
            "page",
            "series_type_index",
        ):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise MangaUpdatesBackfillError(
                    f"{field_name} must be an integer."
                )

        if self.minimum_year < 1:
            raise MangaUpdatesBackfillError(
                "minimum_year must be positive."
            )

        if self.start_year < self.minimum_year:
            raise MangaUpdatesBackfillError(
                "start_year cannot precede minimum_year."
            )

        if not self.minimum_year <= self.current_year <= self.start_year:
            raise MangaUpdatesBackfillError(
                "current_year must be within the checkpoint year range."
            )

        if self.page < 1:
            raise MangaUpdatesBackfillError(
                "page must be positive."
            )

        if not 0 <= self.series_type_index < len(
            MANGAUPDATES_SERIES_TYPES
        ):
            raise MangaUpdatesBackfillError(
                "series_type_index is outside the supported type list."
            )

        if not self.split_by_type and self.series_type_index != 0:
            raise MangaUpdatesBackfillError(
                "An unsplit partition must use series_type_index zero."
            )

        for field_name in (
            "pending_series_ids",
            "pending_recent_series_ids",
            "excluded_recent_series_ids",
        ):
            values = tuple(dict.fromkeys(getattr(self, field_name)))

            if any(
                isinstance(series_id, bool)
                or not isinstance(series_id, int)
                or series_id < 1
                for series_id in values
            ):
                raise MangaUpdatesBackfillError(
                    f"{field_name} must contain positive integers."
                )

            object.__setattr__(self, field_name, values)

    @classmethod
    def initial(
        cls,
        *,
        start_year: int,
        minimum_year: int = DEFAULT_MINIMUM_PUBLICATION_YEAR,
    ) -> MangaUpdatesBackfillCheckpoint:
        return cls(
            start_year=start_year,
            current_year=start_year,
            minimum_year=minimum_year,
        )

    @property
    def series_type(self) -> str | None:
        if not self.split_by_type:
            return None

        return MANGAUPDATES_SERIES_TYPES[
            self.series_type_index
        ]

    @property
    def partition_label(self) -> str:
        if self.complete:
            return "complete"

        suffix = self.series_type or "all-types"
        return f"year={self.current_year},type={suffix},page={self.page}"

    def with_pending_series_ids(
        self,
        series_ids: tuple[int, ...],
    ) -> MangaUpdatesBackfillCheckpoint:
        return replace(
            self,
            pending_series_ids=tuple(dict.fromkeys(series_ids)),
        )

    def with_pending_recent_series_ids(
        self,
        series_ids: tuple[int, ...],
    ) -> MangaUpdatesBackfillCheckpoint:
        return replace(
            self,
            pending_recent_series_ids=tuple(
                dict.fromkeys(series_ids)
            ),
        )

    def with_excluded_recent_series_ids(
        self,
        series_ids: tuple[int, ...],
    ) -> MangaUpdatesBackfillCheckpoint:
        """Remember exclusions only while a series is in the recent window."""
        return replace(self, excluded_recent_series_ids=series_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CATALOG_BACKFILL_SCHEMA_VERSION,
            "provider": "mangaupdates",
            "start_year": self.start_year,
            "current_year": self.current_year,
            "minimum_year": self.minimum_year,
            "page": self.page,
            "split_by_type": self.split_by_type,
            "series_type_index": self.series_type_index,
            "pending_series_ids": list(self.pending_series_ids),
            "pending_recent_series_ids": list(
                self.pending_recent_series_ids
            ),
            "excluded_recent_series_ids": list(self.excluded_recent_series_ids),
            "complete": self.complete,
        }

    @classmethod
    def from_dict(
        cls,
        payload: object,
    ) -> MangaUpdatesBackfillCheckpoint:
        if not isinstance(payload, dict):
            raise MangaUpdatesBackfillError(
                "Catalog checkpoint must be an object."
            )

        if payload.get("schema_version") != (
            CATALOG_BACKFILL_SCHEMA_VERSION
        ):
            raise MangaUpdatesBackfillError(
                "Unsupported catalog checkpoint schema version."
            )

        if payload.get("provider") != "mangaupdates":
            raise MangaUpdatesBackfillError(
                "Catalog checkpoint provider must be mangaupdates."
            )

        split_by_type = payload.get("split_by_type")
        complete = payload.get("complete")

        if not isinstance(split_by_type, bool):
            raise MangaUpdatesBackfillError(
                "split_by_type must be a boolean."
            )

        if not isinstance(complete, bool):
            raise MangaUpdatesBackfillError(
                "complete must be a boolean."
            )

        pending_series_ids = _positive_series_ids(
            payload.get("pending_series_ids")
        )
        legacy_review_series_ids = _positive_series_ids(
            payload.get("review_series_ids", []),
            field_name="review_series_ids",
        )

        return cls(
            start_year=payload.get("start_year"),
            current_year=payload.get("current_year"),
            minimum_year=payload.get("minimum_year"),
            page=payload.get("page"),
            split_by_type=split_by_type,
            series_type_index=payload.get("series_type_index"),
            pending_series_ids=tuple(dict.fromkeys((
                *pending_series_ids,
                *legacy_review_series_ids,
            ))),
            pending_recent_series_ids=_positive_series_ids(
                payload.get("pending_recent_series_ids", []),
                field_name="pending_recent_series_ids",
            ),
            excluded_recent_series_ids=_positive_series_ids(
                payload.get("excluded_recent_series_ids", []),
                field_name="excluded_recent_series_ids",
            ),
            complete=complete,
        )


def _next_year(
    checkpoint: MangaUpdatesBackfillCheckpoint,
) -> MangaUpdatesBackfillCheckpoint:
    next_year = checkpoint.current_year - 1

    if next_year < checkpoint.minimum_year:
        return replace(
            checkpoint,
            page=1,
            split_by_type=False,
            series_type_index=0,
            complete=True,
        )

    return replace(
        checkpoint,
        current_year=next_year,
        page=1,
        split_by_type=False,
        series_type_index=0,
    )


def _next_partition(
    checkpoint: MangaUpdatesBackfillCheckpoint,
) -> MangaUpdatesBackfillCheckpoint:
    if not checkpoint.split_by_type:
        return _next_year(checkpoint)

    next_type_index = checkpoint.series_type_index + 1

    if next_type_index < len(MANGAUPDATES_SERIES_TYPES):
        return replace(
            checkpoint,
            page=1,
            series_type_index=next_type_index,
        )

    return _next_year(checkpoint)


def advance_backfill_page(
    checkpoint: MangaUpdatesBackfillCheckpoint,
    page: MangaUpdatesDiscoveryPage,
) -> tuple[MangaUpdatesBackfillCheckpoint, tuple[int, ...]]:
    """Advance one partition page and return IDs safe to queue."""
    if checkpoint.complete:
        raise MangaUpdatesBackfillError(
            "A complete checkpoint cannot accept another page."
        )

    if page.page != checkpoint.page:
        raise MangaUpdatesBackfillError(
            (
                f"Expected historical page {checkpoint.page}, "
                f"received {page.page}."
            )
        )

    if (
        checkpoint.page == 1
        and page.total_hits >= MANGAUPDATES_SEARCH_RESULT_CAP
    ):
        if checkpoint.split_by_type:
            raise MangaUpdatesBackfillPartitionLimitError(
                (
                    "MangaUpdates capped historical partition "
                    f"{checkpoint.partition_label}; a narrower "
                    "partition is required."
                )
            )

        return (
            replace(
                checkpoint,
                page=1,
                split_by_type=True,
                series_type_index=0,
            ),
            (),
        )

    discovered_ids = tuple(
        item.series_id for item in page.series
    )

    if page.has_more:
        return replace(
            checkpoint,
            page=checkpoint.page + 1,
        ), discovered_ids

    return _next_partition(checkpoint), discovered_ids
