from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.cli.ingest_mangaupdates as cli
from backend.services.ingestion_service import (
    MangaIngestionResult,
)


@pytest.mark.asyncio
async def test_run_series_ingestion_wires_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manga_db = MagicMock()
    provider_closed = False

    async def provide_manga_db():
        nonlocal provider_closed

        try:
            yield manga_db
        finally:
            provider_closed = True

    client = MagicMock()
    client.__aenter__ = AsyncMock(
        return_value=client
    )
    client.__aexit__ = AsyncMock(
        return_value=None
    )

    client_factory = MagicMock(
        return_value=client
    )
    expected = MangaIngestionResult(
        manga_id=17,
        created=True,
        changed=True,
    )
    ingest = AsyncMock(return_value=expected)
    dispose = AsyncMock()

    monkeypatch.setattr(
        cli,
        "get_manga_write_db",
        provide_manga_db,
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

    result = await cli.run_series_ingestion(42)

    assert result == expected
    assert provider_closed is True

    client_factory.assert_called_once_with()
    client.__aenter__.assert_awaited_once_with()
    client.__aexit__.assert_awaited_once()

    ingest.assert_awaited_once_with(
        manga_db,
        client=client,
        series_id=42,
    )
    dispose.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (
            MangaIngestionResult(
                manga_id=17,
                created=True,
                changed=True,
            ),
            "created",
        ),
        (
            MangaIngestionResult(
                manga_id=17,
                created=False,
                changed=True,
            ),
            "updated",
        ),
        (
            MangaIngestionResult(
                manga_id=17,
                created=False,
                changed=False,
            ),
            "unchanged",
        ),
    ],
)
def test_main_reports_successful_outcome(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: MangaIngestionResult,
    status: str,
) -> None:
    validate = MagicMock()
    run_ingestion = AsyncMock(
        return_value=result
    )

    monkeypatch.setattr(
        cli,
        "validate_database_config",
        validate,
    )
    monkeypatch.setattr(
        cli,
        "run_series_ingestion",
        run_ingestion,
    )

    exit_code = cli.main(["42"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out == (
        f"MangaUpdates series 42 {status}; "
        "manga_id=17.\n"
    )

    validate.assert_called_once_with()
    run_ingestion.assert_awaited_once_with(42)


def test_main_returns_one_on_ingestion_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "validate_database_config",
        MagicMock(),
    )
    monkeypatch.setattr(
        cli,
        "run_series_ingestion",
        AsyncMock(
            side_effect=RuntimeError(
                "upstream unavailable"
            )
        ),
    )

    exit_code = cli.main(["42"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == (
        "Ingestion failed: upstream unavailable\n"
    )


@pytest.mark.parametrize(
    "invalid_value",
    [
        "0",
        "not-an-id",
    ],
)
def test_main_rejects_invalid_series_id(
    monkeypatch: pytest.MonkeyPatch,
    invalid_value: str,
) -> None:
    run_ingestion = AsyncMock()

    monkeypatch.setattr(
        cli,
        "run_series_ingestion",
        run_ingestion,
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main([invalid_value])

    assert exc_info.value.code == 2
    run_ingestion.assert_not_awaited()