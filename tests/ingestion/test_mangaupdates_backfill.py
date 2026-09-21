from __future__ import annotations

from dataclasses import replace

import pytest

from backend.clients.mangaupdates_client import (
    MANGAUPDATES_SERIES_TYPES,
)
from backend.ingestion.mangaupdates_backfill import (
    MangaUpdatesBackfillCheckpoint,
    MangaUpdatesBackfillError,
    MangaUpdatesBackfillPartitionLimitError,
    advance_backfill_page,
)
from backend.ingestion.mangaupdates_discovery import (
    MangaUpdatesDiscoveryPage,
)
from tests.ingestion.test_mangaupdates_discovery import (
    page_payload,
    search_result,
)


def _page(
    page: int,
    *series_ids: int,
    total_hits: int,
    per_page: int = 2,
) -> MangaUpdatesDiscoveryPage:
    return MangaUpdatesDiscoveryPage.from_payload(
        page_payload(
            page,
            [
                search_result(series_id, f"Series {series_id}")
                for series_id in series_ids
            ],
            total_hits=total_hits,
            per_page=per_page,
        ),
        expected_page=page,
    )


def test_checkpoint_round_trips_and_deduplicates_pending_ids() -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint(
        start_year=2026,
        current_year=2024,
        page=3,
        split_by_type=True,
        series_type_index=2,
        pending_series_ids=(5, 5, 7),
        pending_recent_series_ids=(8, 8, 9),
        excluded_recent_series_ids=(11, 11, 12),
    )

    restored = MangaUpdatesBackfillCheckpoint.from_dict(
        checkpoint.to_dict()
    )

    assert restored == replace(
        checkpoint,
        pending_series_ids=(5, 7),
        pending_recent_series_ids=(8, 9),
        excluded_recent_series_ids=(11, 12),
    )
    assert restored.series_type == MANGAUPDATES_SERIES_TYPES[2]


def test_old_checkpoint_loads_without_exclusion_field() -> None:
    payload = MangaUpdatesBackfillCheckpoint.initial(start_year=2026).to_dict()
    del payload["excluded_recent_series_ids"]
    del payload["pending_recent_series_ids"]

    checkpoint = MangaUpdatesBackfillCheckpoint.from_dict(payload)
    assert checkpoint.excluded_recent_series_ids == ()
    assert checkpoint.pending_recent_series_ids == ()


def test_legacy_review_ids_return_to_pending_queue() -> None:
    payload = MangaUpdatesBackfillCheckpoint(
        start_year=2026,
        current_year=2026,
        pending_series_ids=(10, 20),
    ).to_dict()
    payload["review_series_ids"] = [20, 30]

    checkpoint = MangaUpdatesBackfillCheckpoint.from_dict(payload)

    assert checkpoint.pending_series_ids == (10, 20, 30)
    assert "review_series_ids" not in checkpoint.to_dict()


def test_capped_year_switches_to_type_partitions_without_queueing(
) -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
    )

    advanced, series_ids = advance_backfill_page(
        checkpoint,
        _page(1, 1, 2, total_hits=10_000),
    )

    assert advanced.current_year == 2026
    assert advanced.split_by_type is True
    assert advanced.series_type_index == 0
    assert advanced.page == 1
    assert series_ids == ()


def test_uncapped_partition_advances_pages_then_year() -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
        minimum_year=2025,
    )

    checkpoint, first_ids = advance_backfill_page(
        checkpoint,
        _page(1, 1, 2, total_hits=3),
    )
    checkpoint, second_ids = advance_backfill_page(
        checkpoint,
        _page(2, 3, total_hits=3),
    )

    assert first_ids == (1, 2)
    assert second_ids == (3,)
    assert checkpoint.current_year == 2025
    assert checkpoint.page == 1
    assert checkpoint.split_by_type is False


def test_last_type_at_minimum_year_completes_backfill() -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint(
        start_year=2026,
        current_year=1900,
        minimum_year=1900,
        split_by_type=True,
        series_type_index=len(MANGAUPDATES_SERIES_TYPES) - 1,
    )

    completed, series_ids = advance_backfill_page(
        checkpoint,
        _page(1, total_hits=0),
    )

    assert series_ids == ()
    assert completed.complete is True
    assert completed.partition_label == "complete"


def test_capped_year_and_type_partition_fails_instead_of_skipping(
) -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint(
        start_year=2026,
        current_year=2026,
        split_by_type=True,
    )

    with pytest.raises(
        MangaUpdatesBackfillPartitionLimitError,
        match="narrower partition",
    ):
        advance_backfill_page(
            checkpoint,
            _page(1, 1, 2, total_hits=10_000),
        )


@pytest.mark.parametrize(
    "field_name",
    ["pending_series_ids", "pending_recent_series_ids"],
)
def test_checkpoint_rejects_invalid_pending_ids(
    field_name: str,
) -> None:
    payload = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
    ).to_dict()
    payload[field_name] = [0]

    with pytest.raises(
        MangaUpdatesBackfillError,
        match="positive integers",
    ):
        MangaUpdatesBackfillCheckpoint.from_dict(payload)
