from __future__ import annotations

import argparse
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest

from backend.cli import sync_mangaupdates_catalog as cli
from backend.ingestion.mangaupdates_backfill import (
    MangaUpdatesBackfillCheckpoint,
)
from backend.ingestion.mangaupdates_discovery import (
    MangaUpdatesDiscoveredSeries,
    MangaUpdatesDiscoveryIssue,
    MangaUpdatesDiscoveryRequest,
    MangaUpdatesDiscoveryState,
)
from backend.services.ingestion_service import (
    MangaIngestionResult,
)


class _ClientContext:
    def __init__(self, client) -> None:
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        return None


def _discovered(series_id: int) -> MangaUpdatesDiscoveredSeries:
    return MangaUpdatesDiscoveredSeries(
        series_id=series_id,
        title=f"Series {series_id}",
        media_type="Manga",
        year="2026",
        source_url=(
            "https://www.mangaupdates.com/series/"
            f"{series_id}"
        ),
        source_updated_at="2026-09-15T12:00:00Z",
    )


def _recent_state(*series_ids: int) -> MangaUpdatesDiscoveryState:
    state = MangaUpdatesDiscoveryState(
        request=MangaUpdatesDiscoveryRequest(limit=500)
    )
    state.series = [_discovered(value) for value in series_ids]
    state.pages_completed = 5
    state.status = "complete"
    state.next_page = None
    state.issues = [
        MangaUpdatesDiscoveryIssue(
            page=2,
            result_index=3,
            message="malformed result",
        )
    ]
    return state


def _success_report(
    *series_ids: int,
) -> cli.ingestion_cli.MangaBatchIngestionReport:
    return cli.ingestion_cli.MangaBatchIngestionReport(
        input_series_ids=tuple(series_ids),
        skipped_existing_series_ids=(),
        attempts=tuple(
            cli.ingestion_cli.MangaIngestionAttempt(
                series_id=series_id,
                result=MangaIngestionResult(
                    manga_id=series_id,
                    created=True,
                    changed=True,
                    cover_status="stored",
                ),
            )
            for series_id in series_ids
        ),
    )


def _search_result(series_id: int) -> dict[str, object]:
    return {
        "record": {
            "series_id": series_id,
            "title": f"Series {series_id}",
            "type": "Manga",
            "year": "2026",
            "url": (
                "https://www.mangaupdates.com/series/"
                f"{series_id}"
            ),
            "last_updated": {
                "as_rfc3339": "2026-09-15T12:00:00Z"
            },
        }
    }


def _page_payload(
    page: int,
    *series_ids: int,
    total_hits: int,
    per_page: int = 100,
) -> dict[str, object]:
    return {
        "total_hits": total_hits,
        "page": page,
        "per_page": per_page,
        "results": [_search_result(value) for value in series_ids],
    }


@pytest.mark.parametrize(
    ("parser", "value"),
    [
        (cli._recent_discovery_limit, "0"),
        (cli._recent_discovery_limit, "10001"),
        (cli._max_new, "401"),
        (cli._historical_pages, "21"),
        (cli._per_page, "101"),
        (cli._minimum_year, "invalid"),
    ],
)
def test_bounded_arguments_reject_invalid_values(
    parser,
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parser(value)


@pytest.mark.parametrize(
    "value",
    ["-0.1", "nan", "inf", "not-a-number"],
)
def test_request_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._request_interval(value)


@pytest.mark.asyncio
async def test_catalog_sync_prioritizes_recent_and_persists_deferred(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object()
    client_factory = Mock(
        return_value=_ClientContext(client)
    )
    checkpoint_store = Mock()
    checkpoint_store.load = AsyncMock(return_value=None)
    checkpoint_store.save = AsyncMock()
    advanced_checkpoint = replace(
        MangaUpdatesBackfillCheckpoint.initial(
            start_year=2026,
        ),
        current_year=2025,
    )
    discover_recent = AsyncMock(
        return_value=_recent_state(1, 2, 3)
    )
    discover_historical = AsyncMock(
        return_value=(advanced_checkpoint, (4, 5), 2)
    )
    load_existing = AsyncMock(return_value={"2", "4"})
    ingestion_report = _success_report(1, 3)
    ingest = AsyncMock(return_value=ingestion_report)
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        client_factory,
    )
    monkeypatch.setattr(cli, "_discover_recent", discover_recent)
    monkeypatch.setattr(
        cli,
        "_discover_historical",
        discover_historical,
    )
    monkeypatch.setattr(
        cli,
        "_load_existing_series_ids",
        load_existing,
    )
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        ingest,
    )

    report = await cli.run_catalog_sync(
        checkpoint_store=checkpoint_store,
        max_new=2,
        exclude_genres=("Hentai",),
        min_request_interval_seconds=0.5,
        initial_year=2026,
    )

    assert report.recent_discovered == 3
    assert report.recent_pages == 5
    assert report.recent_malformed == 1
    assert report.historical_pages == 2
    assert report.considered == 5
    assert report.existing == 2
    assert report.new == 3
    assert report.selected_series_ids == (1, 3)
    assert report.deferred == 1
    assert report.checkpoint.pending_series_ids == (5,)
    assert report.ingestion is ingestion_report
    client_factory.assert_called_once_with(
        min_request_interval_seconds=0.5
    )
    discover_recent.assert_awaited_once_with(
        client,
        limit=500,
        per_page=100,
        exclude_genres=("Hentai", "Lolicon", "Shotacon", "Smut"),
    )
    discover_historical.assert_awaited_once()
    load_existing.assert_awaited_once_with((1, 2, 3, 4, 5))
    ingest.assert_awaited_once_with(
        (1, 3),
        min_request_interval_seconds=0.5,
        progress_callback=cli.ingestion_cli._print_batch_progress,
        progress_interval=25,
    )
    assert checkpoint_store.save.await_count == 2
    first_saved = checkpoint_store.save.await_args_list[0].args[0]
    final_saved = checkpoint_store.save.await_args_list[1].args[0]
    assert first_saved.pending_series_ids == (1, 3, 5)
    assert final_saved.pending_series_ids == (5,)


@pytest.mark.asyncio
async def test_preview_advances_only_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
    )
    checkpoint_store = Mock()
    checkpoint_store.load = AsyncMock(return_value=checkpoint)
    checkpoint_store.save = AsyncMock()
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        Mock(return_value=_ClientContext(object())),
    )
    monkeypatch.setattr(
        cli,
        "_discover_recent",
        AsyncMock(return_value=_recent_state(10)),
    )
    monkeypatch.setattr(
        cli,
        "_discover_historical",
        AsyncMock(return_value=(checkpoint, (20,), 1)),
    )
    monkeypatch.setattr(
        cli,
        "_load_existing_series_ids",
        AsyncMock(return_value=set()),
    )
    ingest = AsyncMock()
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        ingest,
    )

    report = await cli.run_catalog_sync(
        checkpoint_store=checkpoint_store,
        preview=True,
        max_new=1,
        initial_year=2026,
    )

    assert report.selected_series_ids == (10,)
    assert report.deferred == 1
    assert report.checkpoint.pending_series_ids == (10, 20)
    assert report.ingestion is None
    checkpoint_store.save.assert_not_awaited()
    ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_historical_discovery_splits_capped_year_by_type() -> None:
    client = Mock()
    client.discover_series_page = AsyncMock(
        side_effect=[
            _page_payload(1, 1, total_hits=10_000),
            _page_payload(1, 42, total_hits=1),
        ]
    )
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
        minimum_year=2025,
    )

    checkpoint, series_ids, pages = await cli._discover_historical(
        client,
        checkpoint=checkpoint,
        max_pages=2,
        per_page=100,
        queue_target=200,
        exclude_genres=("Hentai",),
    )

    assert series_ids == (42,)
    assert pages == 2
    assert checkpoint.current_year == 2026
    assert checkpoint.split_by_type is True
    assert checkpoint.series_type_index == 1
    assert checkpoint.page == 1
    first_call, second_call = (
        client.discover_series_page.await_args_list
    )
    assert first_call.kwargs["series_types"] == ()
    assert second_call.kwargs["series_types"] == ("Artbook",)
    assert second_call.kwargs["year"] == "2026"


@pytest.mark.asyncio
async def test_historical_discovery_waits_when_queue_meets_target(
) -> None:
    client = Mock()
    client.discover_series_page = AsyncMock()
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
    ).with_pending_series_ids((1, 2))

    result_checkpoint, series_ids, pages = (
        await cli._discover_historical(
            client,
            checkpoint=checkpoint,
            max_pages=5,
            per_page=100,
            queue_target=2,
            exclude_genres=(),
        )
    )

    assert result_checkpoint == checkpoint
    assert series_ids == ()
    assert pages == 0
    client.discover_series_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_load_existing_series_ids_uses_one_database_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manga_db = object()

    async def database_provider():
        yield manga_db

    find_existing = AsyncMock(return_value={"10"})
    dispose = AsyncMock()
    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_existing_catalog_external_ids",
        find_existing,
    )
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    result = await cli._load_existing_series_ids((10, 20))

    assert result == {"10"}
    find_existing.assert_awaited_once_with(
        manga_db,
        provider_key="mangaupdates",
        external_ids=("10", "20"),
    )
    dispose.assert_awaited_once_with()


def test_print_preview_reports_both_discovery_tracks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    checkpoint = MangaUpdatesBackfillCheckpoint.initial(
        start_year=2026,
    ).with_pending_series_ids((10, 20))
    report = cli.MangaCatalogSyncReport(
        recent_discovered=500,
        recent_pages=5,
        recent_malformed=1,
        historical_pages=2,
        considered=502,
        existing=499,
        new=3,
        selected_series_ids=(10, 20),
        deferred=1,
        checkpoint=checkpoint,
        ingestion=None,
    )

    assert cli._print_report(report, preview=True) == 0
    assert capsys.readouterr().out == (
        "Catalog preview: recent_discovered=500; recent_pages=5; "
        "recent_malformed=1; historical_pages=2; considered=502; "
        "existing=499; excluded_known=0; new=3; selected=2; deferred=1; "
        "checkpoint=year=2026,type=all-types,page=1; "
        "checkpoint_pending=2.\n"
        "No checkpoint, series details, covers, or records were changed.\n"
    )


def test_completed_ingestion_ids_include_race_skips_and_successes(
) -> None:
    report = _success_report(10)
    report = cli.ingestion_cli.MangaBatchIngestionReport(
        input_series_ids=(10, 20),
        skipped_existing_series_ids=(20,),
        attempts=report.attempts,
    )

    assert cli._completed_ingestion_ids(report) == {10, 20}


@pytest.mark.asyncio
async def test_restricted_recent_series_is_skipped_on_later_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint_store = Mock()
    checkpoint_store.load = AsyncMock(return_value=None)
    checkpoint_store.save = AsyncMock()
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        Mock(return_value=_ClientContext(object())),
    )
    monkeypatch.setattr(
        cli, "_discover_recent", AsyncMock(return_value=_recent_state(10, 20))
    )

    async def no_historical(client, *, checkpoint, **kwargs):
        return checkpoint, (), 0

    monkeypatch.setattr(cli, "_discover_historical", no_historical)
    existing = AsyncMock(return_value=set())
    monkeypatch.setattr(cli, "_load_existing_series_ids", existing)
    excluded = cli.ingestion_cli.MangaIngestionAttempt(
        series_id=10,
        excluded_reason="Explicit genre is excluded from the catalog.",
    )
    created = _success_report(20).attempts[0]
    ingest = AsyncMock(return_value=cli.ingestion_cli.MangaBatchIngestionReport(
        input_series_ids=(10, 20),
        skipped_existing_series_ids=(),
        attempts=(excluded, created),
    ))
    monkeypatch.setattr(cli.ingestion_cli, "run_batch_ingestion", ingest)

    first = await cli.run_catalog_sync(
        checkpoint_store=checkpoint_store,
        max_new=2,
        initial_year=2026,
    )

    assert first.checkpoint.pending_series_ids == ()
    assert first.checkpoint.excluded_recent_series_ids == (10,)

    checkpoint_store.load.return_value = first.checkpoint
    existing.return_value = {"20"}
    second = await cli.run_catalog_sync(
        checkpoint_store=checkpoint_store,
        max_new=2,
        initial_year=2026,
    )

    assert second.selected_series_ids == ()
    assert second.excluded_known == 1
    assert ingest.await_count == 1
