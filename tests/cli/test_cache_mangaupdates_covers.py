from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, call

import pytest

from backend.cli import cache_mangaupdates_covers as cli
from backend.clients.mangaupdates_client import (
    MangaUpdatesRateLimitError,
    MangaUpdatesTransportError,
)
from backend.repositories.ingestion_repo import CatalogCoverCandidate
from backend.services.cover_service import CoverCacheResult
from backend.storage.cover_store import CoverStorageError


class _ClientContext:
    def __init__(self, client: object) -> None:
        self.client = client

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None


def _candidate(
    manga_id: int,
    external_id: str,
) -> CatalogCoverCandidate:
    return CatalogCoverCandidate(
        manga_id=manga_id,
        external_id=external_id,
        source_url=(
            "https://cdn.mangaupdates.com/"
            f"image/i{external_id}.png"
        ),
    )


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_positive_integer_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._positive_integer(value)


@pytest.mark.parametrize(
    "value",
    ["invalid", "-0.1", "nan", "inf"],
)
def test_request_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._request_interval(value)


def test_run_cover_cache_preview_selects_without_external_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manga_db = object()
    store = MagicMock()
    store.public_base_url = "https://mangarecon.com"

    async def database_provider():
        yield manga_db

    find_candidates = AsyncMock(
        return_value=(_candidate(1, "10"), _candidate(2, "20"))
    )
    client_factory = Mock()
    cache = AsyncMock()
    dispose = AsyncMock()
    monkeypatch.setattr(
        cli,
        "create_cover_store_from_settings",
        Mock(return_value=store),
    )
    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_uncached_catalog_covers",
        find_candidates,
    )
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        client_factory,
    )
    monkeypatch.setattr(cli, "cache_catalog_cover", cache)
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    report = asyncio.run(
        cli.run_cover_cache(preview=True, limit=25)
    )

    assert report == cli.CoverCacheReport(
        selected=2,
        attempts=(),
    )
    find_candidates.assert_awaited_once_with(
        manga_db,
        provider_key="mangaupdates",
        public_base_url="https://mangarecon.com",
        limit=25,
    )
    client_factory.assert_not_called()
    cache.assert_not_awaited()
    dispose.assert_awaited_once_with()


def test_run_cover_cache_processes_independent_items_and_reports_progress(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manga_db = object()
    client = object()
    store = MagicMock()
    store.public_base_url = "https://mangarecon.com"
    candidates = (
        _candidate(1, "10"),
        _candidate(2, "20"),
        _candidate(3, "30"),
    )

    async def database_provider():
        yield manga_db

    cache = AsyncMock(
        side_effect=[
            CoverCacheResult(
                manga_id=1,
                external_id="10",
                stored_url="https://stored/10",
                database_updated=True,
            ),
            CoverCacheResult(
                manga_id=2,
                external_id="20",
                stored_url="https://stored/20",
                database_updated=False,
            ),
            RuntimeError("bad image"),
        ]
    )
    dispose = AsyncMock()
    monkeypatch.setattr(
        cli,
        "create_cover_store_from_settings",
        Mock(return_value=store),
    )
    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_uncached_catalog_covers",
        AsyncMock(return_value=candidates),
    )
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        Mock(return_value=_ClientContext(client)),
    )
    monkeypatch.setattr(cli, "cache_catalog_cover", cache)
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    report = asyncio.run(
        cli.run_cover_cache(
            min_request_interval_seconds=0.5,
            progress_interval=2,
        )
    )

    assert report.selected == 3
    assert report.attempts == (
        cli.CoverCacheAttempt(candidates[0], cached=True),
        cli.CoverCacheAttempt(
            candidates[1],
            skipped_changed=True,
        ),
        cli.CoverCacheAttempt(candidates[2], error="bad image"),
    )
    assert cache.await_args_list == [
        call(
            manga_db,
            candidate=candidates[0],
            client=client,
            cover_store=store,
        ),
        call(
            manga_db,
            candidate=candidates[1],
            client=client,
            cover_store=store,
        ),
        call(
            manga_db,
            candidate=candidates[2],
            client=client,
            cover_store=store,
        ),
    ]
    captured = capsys.readouterr()
    assert "processed=2/3; cached=1; skipped_changed=1" in (
        captured.out
    )
    assert "manga_id=3; series_id=30; error=bad image" in (
        captured.err
    )
    dispose.assert_awaited_once_with()


@pytest.mark.parametrize(
    "failure",
    [
        MangaUpdatesTransportError("source unavailable"),
        CoverStorageError("storage unavailable"),
    ],
)
def test_run_cover_cache_stops_after_systemic_failure(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    store = MagicMock()
    store.public_base_url = "https://mangarecon.com"

    async def database_provider():
        yield object()

    cache = AsyncMock(side_effect=failure)
    dispose = AsyncMock()
    monkeypatch.setattr(
        cli,
        "create_cover_store_from_settings",
        Mock(return_value=store),
    )
    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_uncached_catalog_covers",
        AsyncMock(
            return_value=(_candidate(1, "10"), _candidate(2, "20"))
        ),
    )
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        Mock(return_value=_ClientContext(object())),
    )
    monkeypatch.setattr(cli, "cache_catalog_cover", cache)
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    with pytest.raises(type(failure), match=str(failure)):
        asyncio.run(cli.run_cover_cache())

    assert cache.await_count == 1
    dispose.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"limit": 0}, "limit"),
        ({"progress_interval": 0}, "progress_interval"),
    ],
)
def test_run_cover_cache_rejects_invalid_runtime_options(
    arguments: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        asyncio.run(cli.run_cover_cache(**arguments))


def test_main_prints_preview(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    validate = Mock()
    run = AsyncMock(
        return_value=cli.CoverCacheReport(selected=12, attempts=())
    )
    monkeypatch.setattr(cli, "validate_database_config", validate)
    monkeypatch.setattr(cli, "run_cover_cache", run)

    exit_code = cli.main(["--preview", "--limit", "25"])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Cover-cache preview: selected=12; limit=25. "
        "No images were downloaded and no records were changed.\n"
    )
    validate.assert_called_once_with()
    run.assert_awaited_once_with(
        preview=True,
        limit=25,
        min_request_interval_seconds=None,
    )


def test_main_prints_failure_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    attempts = (
        cli.CoverCacheAttempt(_candidate(1, "10"), cached=True),
        cli.CoverCacheAttempt(_candidate(2, "20"), error="bad image"),
    )
    monkeypatch.setattr(
        cli,
        "validate_database_config",
        Mock(),
    )
    monkeypatch.setattr(
        cli,
        "run_cover_cache",
        AsyncMock(
            return_value=cli.CoverCacheReport(
                selected=2,
                attempts=attempts,
            )
        ),
    )

    assert cli.main([]) == 1
    assert capsys.readouterr().out == (
        "Cover-cache summary: selected=2; cached=1; "
        "skipped_changed=0; failed=1.\n"
    )


def test_main_reports_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "validate_database_config",
        Mock(),
    )
    monkeypatch.setattr(
        cli,
        "run_cover_cache",
        AsyncMock(
            side_effect=MangaUpdatesRateLimitError(
                retry_after="30"
            )
        ),
    )

    assert cli.main([]) == 1
    assert capsys.readouterr().err == (
        "Cover caching stopped after MangaUpdates returned HTTP 429; "
        "no further requests were sent. Retry-After=30.\n"
    )


def test_main_handles_interrupt_and_general_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "validate_database_config",
        Mock(side_effect=KeyboardInterrupt),
    )
    assert cli.main([]) == 130
    assert "Completed records remain stored" in capsys.readouterr().err

    monkeypatch.setattr(
        cli,
        "validate_database_config",
        Mock(side_effect=RuntimeError("configuration failed")),
    )
    assert cli.main([]) == 1
    assert "configuration failed" in capsys.readouterr().err
