from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend.cli import refresh_mangaupdates as cli


@pytest.mark.parametrize("value", ["abc", "0", "-1"])
def test_positive_integer_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._positive_integer(value)


@pytest.mark.parametrize(
    "value",
    ["-0.1", "nan", "inf", "not-a-number"],
)
def test_request_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._request_interval(value)


def test_parser_requires_refresh_scope() -> None:
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


@pytest.mark.parametrize("value", ["invalid", "0", "-1"])
def test_stored_series_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(
        RuntimeError,
        match="invalid MangaUpdates external ID",
    ):
        cli._stored_series_id(value)


def test_load_missing_cover_series_ids_uses_writer_and_disposes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manga_db = object()

    async def database_provider():
        yield manga_db

    find_missing = AsyncMock(return_value=("10", "20"))
    dispose = AsyncMock()

    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_missing_cover_external_ids",
        find_missing,
    )
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    result = asyncio.run(
        cli.load_missing_cover_series_ids(limit=25)
    )

    assert result == (10, 20)
    find_missing.assert_awaited_once_with(
        manga_db,
        provider_key="mangaupdates",
        limit=25,
    )
    dispose.assert_awaited_once_with()


def test_load_missing_cover_series_ids_disposes_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def database_provider():
        yield object()

    failure = RuntimeError("selection failed")
    dispose = AsyncMock()

    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "find_missing_cover_external_ids",
        AsyncMock(side_effect=failure),
    )
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    with pytest.raises(RuntimeError, match="selection failed"):
        asyncio.run(cli.load_missing_cover_series_ids())

    dispose.assert_awaited_once_with()


def test_main_previews_missing_cover_selection_without_refreshing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    validate = Mock()
    load = AsyncMock(return_value=(10, 20))
    refresh = AsyncMock()

    monkeypatch.setattr(cli, "validate_database_config", validate)
    monkeypatch.setattr(
        cli,
        "load_missing_cover_series_ids",
        load,
    )
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        refresh,
    )

    exit_code = cli.main(
        [
            "--missing-covers",
            "--preview",
            "--limit",
            "25",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "Missing-cover refresh preview: selected=2; limit=25. "
        "No records were changed.\n"
    )
    validate.assert_called_once_with()
    load.assert_awaited_once_with(limit=25)
    refresh.assert_not_awaited()


def test_main_reports_when_no_missing_covers_exist(
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
        "load_missing_cover_series_ids",
        AsyncMock(return_value=()),
    )
    refresh = AsyncMock()
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        refresh,
    )

    assert cli.main(["--missing-covers"]) == 0
    assert capsys.readouterr().out == (
        "No MangaUpdates manga with missing covers were found.\n"
    )
    refresh.assert_not_awaited()


def test_main_refreshes_selected_records_with_full_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = Mock()
    refresh = AsyncMock(return_value=report)
    print_results = Mock(return_value=1)

    monkeypatch.setattr(
        cli,
        "validate_database_config",
        Mock(),
    )
    monkeypatch.setattr(
        cli,
        "load_missing_cover_series_ids",
        AsyncMock(return_value=(10, 20)),
    )
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        refresh,
    )
    monkeypatch.setattr(
        cli.ingestion_cli,
        "_print_batch_results",
        print_results,
    )

    exit_code = cli.main(
        [
            "--missing-covers",
            "--min-request-interval-seconds",
            "0.5",
        ]
    )

    assert exit_code == 1
    refresh.assert_awaited_once_with(
        (10, 20),
        min_request_interval_seconds=0.5,
        refresh_existing=True,
        progress_callback=cli.ingestion_cli._print_batch_progress,
    )
    print_results.assert_called_once_with(report)


def test_main_reports_rate_limit_and_resume_guidance(
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
        "load_missing_cover_series_ids",
        AsyncMock(return_value=(10, 20)),
    )
    monkeypatch.setattr(
        cli.ingestion_cli,
        "run_batch_ingestion",
        AsyncMock(
            side_effect=cli.ingestion_cli.MangaUpdatesRateLimitError(
                retry_after="30"
            )
        ),
    )

    assert cli.main(["--missing-covers"]) == 1
    assert capsys.readouterr().err == (
        "Refresh stopped after MangaUpdates returned HTTP 429; "
        "no further requests were sent. Retry-After=30. "
        "Rerun later to continue.\n"
    )


def test_main_handles_keyboard_interrupt(
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
        "load_missing_cover_series_ids",
        AsyncMock(side_effect=KeyboardInterrupt),
    )

    assert cli.main(["--missing-covers"]) == 130
    assert capsys.readouterr().err == (
        "Refresh interrupted by user. Already completed records "
        "remain committed; rerun the same command to continue.\n"
    )


def test_main_reports_selection_failure(
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
        "load_missing_cover_series_ids",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )

    assert cli.main(["--missing-covers"]) == 1
    assert capsys.readouterr().err == (
        "Refresh failed: database unavailable\n"
    )
