from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.ingestion.mangaupdates_discovery import (
    MangaUpdatesDiscoveryError,
    MangaUpdatesDiscoveryRequest,
    MangaUpdatesDiscoveryRunError,
    MangaUpdatesDiscoveryState,
    discover_mangaupdates_catalog,
)


def search_result(
    series_id: int,
    title: str,
    *,
    media_type: str = "Manga",
    year: str = "2020",
) -> dict[str, object]:
    return {
        "record": {
            "series_id": series_id,
            "title": title,
            "type": media_type,
            "year": year,
            "url": (
                "https://www.mangaupdates.com/series/"
                f"{series_id}"
            ),
            "last_updated": {
                "as_rfc3339": "2026-08-01T12:00:00Z"
            },
        }
    }


def page_payload(
    page: int,
    results: list[object],
    *,
    total_hits: int = 4,
    per_page: int = 2,
) -> dict[str, object]:
    return {
        "total_hits": total_hits,
        "page": page,
        "per_page": per_page,
        "results": results,
    }


def client_with_pages(*pages_or_errors: object):
    return SimpleNamespace(
        discover_series_page=AsyncMock(
            side_effect=list(pages_or_errors)
        )
    )


@pytest.mark.asyncio
async def test_discovery_paginates_and_deduplicates_in_first_seen_order(
) -> None:
    client = client_with_pages(
        page_payload(
            1,
            [search_result(1, "One"), search_result(2, "Two")],
        ),
        page_payload(
            2,
            [search_result(2, "Two"), search_result(3, "Three")],
        ),
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=3,
            per_page=2,
            series_types=("Manga", "Manhwa"),
            year="2020",
            genres=("Action",),
            exclude_genres=("Hentai",),
            filters=("completed",),
            order_by="rating",
        )
    )
    checkpoints: list[dict[str, object]] = []

    result = await discover_mangaupdates_catalog(
        client,  # type: ignore[arg-type]
        state=state,
        checkpoint=lambda current: checkpoints.append(
            current.to_dict()
        ),
    )

    assert result.status == "complete"
    assert result.next_page is None
    assert result.pages_completed == 2
    assert [item.series_id for item in result.series] == [
        1,
        2,
        3,
    ]
    assert len(checkpoints) == 2
    assert client.discover_series_page.await_count == 2
    client.discover_series_page.assert_any_await(
        query=None,
        page=1,
        per_page=2,
        series_types=("Manga", "Manhwa"),
        year="2020",
        genres=("Action",),
        exclude_genres=("Hentai",),
        filters=("completed",),
        order_by="rating",
    )


@pytest.mark.asyncio
async def test_malformed_results_are_recorded_without_losing_valid_items(
) -> None:
    client = client_with_pages(
        page_payload(
            1,
            [
                search_result(1, "One"),
                {},
                {
                    "record": {
                        "series_id": 0,
                        "title": "Invalid",
                    }
                },
            ],
            total_hits=3,
            per_page=3,
        )
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(limit=10)
    )

    result = await discover_mangaupdates_catalog(
        client,  # type: ignore[arg-type]
        state=state,
    )

    assert result.status == "complete"
    assert [item.series_id for item in result.series] == [1]
    assert len(result.issues) == 2
    assert result.issues[0].page == 1
    assert result.issues[0].result_index == 1
    assert "result.record" in result.issues[0].message
    assert result.issues[1].result_index == 2
    assert "series_id" in result.issues[1].message


@pytest.mark.asyncio
async def test_page_failure_preserves_partial_results_for_resume(
) -> None:
    client = client_with_pages(
        page_payload(
            1,
            [search_result(1, "One"), search_result(2, "Two")],
        ),
        RuntimeError("temporary upstream failure"),
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=4,
            per_page=2,
        )
    )
    checkpoints: list[dict[str, object]] = []

    with pytest.raises(
        MangaUpdatesDiscoveryRunError,
        match="temporary upstream failure",
    ):
        await discover_mangaupdates_catalog(
            client,  # type: ignore[arg-type]
            state=state,
            checkpoint=lambda current: checkpoints.append(
                current.to_dict()
            ),
        )

    assert state.status == "failed"
    assert state.next_page == 2
    assert state.pages_completed == 1
    assert [item.series_id for item in state.series] == [1, 2]
    assert state.last_error == "temporary upstream failure"
    assert checkpoints[-1]["status"] == "failed"
    assert checkpoints[-1]["next_page"] == 2


@pytest.mark.asyncio
async def test_interruption_leaves_last_successful_checkpoint_resumable(
) -> None:
    client = client_with_pages(
        page_payload(
            1,
            [search_result(1, "One"), search_result(2, "Two")],
        ),
        asyncio.CancelledError(),
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=4,
            per_page=2,
        )
    )
    checkpoints: list[dict[str, object]] = []

    with pytest.raises(asyncio.CancelledError):
        await discover_mangaupdates_catalog(
            client,  # type: ignore[arg-type]
            state=state,
            checkpoint=lambda current: checkpoints.append(
                current.to_dict()
            ),
        )

    assert state.status == "in_progress"
    assert state.next_page == 2
    assert state.pages_completed == 1
    assert len(checkpoints) == 1
    assert checkpoints[0]["next_page"] == 2


@pytest.mark.asyncio
async def test_saved_checkpoint_resumes_at_next_page(
) -> None:
    interrupted_client = client_with_pages(
        page_payload(
            1,
            [search_result(1, "One"), search_result(2, "Two")],
        ),
        asyncio.CancelledError(),
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(
            limit=4,
            per_page=2,
        )
    )
    checkpoints: list[dict[str, object]] = []

    with pytest.raises(asyncio.CancelledError):
        await discover_mangaupdates_catalog(
            interrupted_client,  # type: ignore[arg-type]
            state=state,
            checkpoint=lambda current: checkpoints.append(
                current.to_dict()
            ),
        )

    resumed = MangaUpdatesDiscoveryState.from_dict(
        checkpoints[-1]
    )
    resume_client = client_with_pages(
        page_payload(
            2,
            [
                search_result(3, "Three"),
                search_result(4, "Four"),
            ],
        )
    )

    result = await discover_mangaupdates_catalog(
        resume_client,  # type: ignore[arg-type]
        state=resumed,
    )

    assert result.status == "complete"
    assert [item.series_id for item in result.series] == [
        1,
        2,
        3,
        4,
    ]
    resume_client.discover_series_page.assert_awaited_once()
    assert (
        resume_client.discover_series_page.await_args.kwargs["page"]
        == 2
    )


@pytest.mark.asyncio
async def test_malformed_page_marks_checkpoint_failed(
) -> None:
    client = client_with_pages(
        {
            "page": 1,
            "per_page": 100,
            "results": [],
        }
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest()
    )
    checkpoints: list[dict[str, object]] = []

    with pytest.raises(
        MangaUpdatesDiscoveryRunError,
        match="total_hits",
    ):
        await discover_mangaupdates_catalog(
            client,  # type: ignore[arg-type]
            state=state,
            checkpoint=lambda current: checkpoints.append(
                current.to_dict()
            ),
        )

    assert state.status == "failed"
    assert state.next_page == 1
    assert checkpoints[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_upstream_error_object_preserves_reason_in_checkpoint(
) -> None:
    client = client_with_pages(
        {
            "status": "exception",
            "reason": "Temporary search failure",
        }
    )
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest()
    )
    checkpoints: list[dict[str, object]] = []

    with pytest.raises(
        MangaUpdatesDiscoveryRunError,
        match="Temporary search failure",
    ):
        await discover_mangaupdates_catalog(
            client,  # type: ignore[arg-type]
            state=state,
            checkpoint=lambda current: checkpoints.append(
                current.to_dict()
            ),
        )

    assert checkpoints[-1]["last_error"] == (
        "MangaUpdates discovery error: Temporary search failure"
    )


def test_manifest_round_trip_validates_series_count() -> None:
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(limit=1)
    )
    state_payload = state.to_dict()
    state_payload["series_count"] = 1

    with pytest.raises(
        MangaUpdatesDiscoveryError,
        match="series_count does not match",
    ):
        MangaUpdatesDiscoveryState.from_dict(state_payload)
