from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from backend.cli import ingest_mangaupdates as cli
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


def _result(
    manga_id: int,
    *,
    created: bool = False,
    changed: bool = False,
) -> MangaIngestionResult:
    return MangaIngestionResult(
        manga_id=manga_id,
        created=created,
        changed=changed,
    )


@pytest.mark.parametrize("value", ["abc", "0", "-1"])
def test_series_id_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._series_id(value)


@pytest.mark.parametrize(
    "value",
    ["-0.1", "nan", "inf", "not-a-number"],
)
def test_request_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._request_interval(value)


def test_load_series_ids_supports_comments_and_bom(
    tmp_path,
) -> None:
    input_file = tmp_path / "series.txt"
    input_file.write_text(
        "\ufeff# sample\n17360452316\n\n15180124327 # note\n",
        encoding="utf-8",
    )

    assert cli._load_series_ids(input_file) == [
        17360452316,
        15180124327,
    ]


def test_load_series_ids_reports_invalid_line(
    tmp_path,
) -> None:
    input_file = tmp_path / "series.txt"
    input_file.write_text("1\ninvalid\n", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=r"series\.txt:2: series ID must be an integer",
    ):
        cli._load_series_ids(input_file)


def test_collect_series_ids_deduplicates_in_first_seen_order(
    tmp_path,
) -> None:
    input_file = tmp_path / "series.txt"
    input_file.write_text("2\n3\n1\n", encoding="utf-8")

    assert cli._collect_series_ids(
        [1, 2, 1],
        input_file,
    ) == (1, 2, 3)


def test_run_batch_ingestion_isolates_failures_and_reuses_resources(
    monkeypatch,
) -> None:
    manga_db = object()
    client = object()

    async def database_provider():
        yield manga_db

    client_factory = Mock(
        return_value=_ClientContext(client)
    )
    ingest = AsyncMock(
        side_effect=[
            _result(10, created=True, changed=True),
            RuntimeError("bad payload"),
            _result(12),
        ]
    )
    dispose = AsyncMock()

    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        database_provider,
    )
    monkeypatch.setattr(
        cli,
        "create_mangaupdates_client",
        client_factory,
    )
    monkeypatch.setattr(
        cli,
        "ingest_mangaupdates_series",
        ingest,
    )
    monkeypatch.setattr(
        cli,
        "dispose_database_engines",
        dispose,
    )

    attempts = asyncio.run(
        cli.run_batch_ingestion(
            [10, 11, 12],
            min_request_interval_seconds=0.25,
        )
    )

    assert [attempt.series_id for attempt in attempts] == [
        10,
        11,
        12,
    ]
    assert attempts[0].result == _result(
        10,
        created=True,
        changed=True,
    )
    assert attempts[1].error == "bad payload"
    assert attempts[2].result == _result(12)
    assert ingest.await_count == 3
    client_factory.assert_called_once_with(
        min_request_interval_seconds=0.25
    )
    dispose.assert_awaited_once_with()


def test_main_preserves_single_series_output(
    monkeypatch,
    capsys,
) -> None:
    validate = Mock()
    ingest = AsyncMock(
        return_value=_result(
            8,
            created=True,
            changed=True,
        )
    )

    monkeypatch.setattr(
        cli,
        "validate_database_config",
        validate,
    )
    monkeypatch.setattr(
        cli,
        "run_series_ingestion",
        ingest,
    )

    exit_code = cli.main(["17360452316"])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "MangaUpdates series 17360452316 created; "
        "manga_id=8.\n"
    )
    validate.assert_called_once_with()
    ingest.assert_awaited_once_with(17360452316)


def test_main_reports_batch_summary_and_failure_exit_code(
    monkeypatch,
    capsys,
) -> None:
    validate = Mock()
    ingest = AsyncMock(
        return_value=(
            cli.MangaIngestionAttempt(
                series_id=1,
                result=_result(
                    8,
                    created=True,
                    changed=True,
                ),
            ),
            cli.MangaIngestionAttempt(
                series_id=2,
                error="not found",
            ),
        )
    )

    monkeypatch.setattr(
        cli,
        "validate_database_config",
        validate,
    )
    monkeypatch.setattr(
        cli,
        "run_batch_ingestion",
        ingest,
    )

    exit_code = cli.main(["1", "1", "2"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == (
        "MangaUpdates series 1 created; manga_id=8.\n"
        "Summary: total=2; created=1; updated=0; "
        "unchanged=0; failed=1.\n"
    )
    assert captured.err == (
        "MangaUpdates series 2 failed: not found\n"
    )
    validate.assert_called_once_with()
    ingest.assert_awaited_once_with((1, 2))
