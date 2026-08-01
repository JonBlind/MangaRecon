from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.services.ingestion_service as service
from backend.db.models.manga import Manga
from backend.repositories.ingestion_repo import (
    CatalogUpsertOutcome,
)


@pytest.mark.asyncio
async def test_changed_ingestion_is_committed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    user_db.commit = AsyncMock()
    user_db.rollback = AsyncMock()

    record = MagicMock()
    manga = Manga(
        manga_id=17,
        title="Berserk",
    )
    upsert = AsyncMock(
        return_value=CatalogUpsertOutcome(
            manga=manga,
            created=True,
            changed=True,
        )
    )

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda payload: record,
    )
    monkeypatch.setattr(
        service,
        "upsert_catalog_manga",
        upsert,
    )

    result = await service.ingest_mangaupdates_payload(
        user_db,
        payload={"series_id": 1},
    )

    assert result.manga_id == 17
    assert result.created is True
    assert result.changed is True

    user_db.commit.assert_awaited_once_with()
    user_db.rollback.assert_not_awaited()

    assert upsert.await_args.kwargs == {
        "record": record,
        "provider_display_name": "MangaUpdates",
        "provider_attribution_url": (
            "https://www.mangaupdates.com/"
        ),
    }


@pytest.mark.asyncio
async def test_unchanged_ingestion_is_not_committed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    user_db.commit = AsyncMock()
    user_db.rollback = AsyncMock()

    manga = Manga(
        manga_id=17,
        title="Berserk",
    )

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda payload: MagicMock(),
    )
    monkeypatch.setattr(
        service,
        "upsert_catalog_manga",
        AsyncMock(
            return_value=CatalogUpsertOutcome(
                manga=manga,
                created=False,
                changed=False,
            )
        ),
    )

    result = await service.ingest_mangaupdates_payload(
        user_db,
        payload={"series_id": 1},
    )

    assert result == service.MangaIngestionResult(
        manga_id=17,
        created=False,
        changed=False,
    )
    user_db.commit.assert_not_awaited()
    user_db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_persistence_failure_is_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    user_db.commit = AsyncMock()
    user_db.rollback = AsyncMock()

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda payload: MagicMock(),
    )
    monkeypatch.setattr(
        service,
        "upsert_catalog_manga",
        AsyncMock(
            side_effect=RuntimeError(
                "database failure"
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="database failure",
    ):
        await service.ingest_mangaupdates_payload(
            user_db,
            payload={"series_id": 1},
        )

    user_db.commit.assert_not_awaited()
    user_db.rollback.assert_awaited_once_with()

@pytest.mark.asyncio
async def test_series_ingestion_fetches_and_ingests_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    payload = {
        "series_id": 42,
        "title": "Berserk",
    }

    client = MagicMock()
    client.get_series = AsyncMock(
        return_value=payload
    )

    expected = service.MangaIngestionResult(
        manga_id=17,
        created=True,
        changed=True,
    )
    ingest_payload = AsyncMock(
        return_value=expected
    )

    monkeypatch.setattr(
        service,
        "ingest_mangaupdates_payload",
        ingest_payload,
    )

    result = await service.ingest_mangaupdates_series(
        user_db,
        client=client,
        series_id=42,
    )

    assert result == expected
    client.get_series.assert_awaited_once_with(42)
    ingest_payload.assert_awaited_once_with(
        user_db,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_series_fetch_failure_skips_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()

    client = MagicMock()
    client.get_series = AsyncMock(
        side_effect=RuntimeError("upstream failure")
    )
    ingest_payload = AsyncMock()

    monkeypatch.setattr(
        service,
        "ingest_mangaupdates_payload",
        ingest_payload,
    )

    with pytest.raises(
        RuntimeError,
        match="upstream failure",
    ):
        await service.ingest_mangaupdates_series(
            user_db,
            client=client,
            series_id=42,
        )

    ingest_payload.assert_not_awaited()