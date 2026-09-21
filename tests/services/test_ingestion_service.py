from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import backend.services.ingestion_service as service
from backend.clients.mangaupdates_client import (
    MangaUpdatesHTTPError,
    MangaUpdatesRateLimitError,
    MangaUpdatesTransportError,
)
from backend.content_safety.policy import CatalogContentExcluded
from backend.db.models.manga import Manga
from backend.ingestion.images import DownloadedCoverImage
from backend.ingestion.records import MangaIngestionRecord
from backend.repositories.ingestion_repo import (
    CatalogUpsertOutcome,
)
from backend.storage.cover_store import CoverStorageError


def _record(
    *,
    cover_image_url: str | None = (
        "https://cdn.mangaupdates.com/image/i42.png"
    ),
) -> MangaIngestionRecord:
    return MangaIngestionRecord(
        provider_key="mangaupdates",
        external_id="42",
        source_url="https://www.mangaupdates.com/series/42",
        source_updated_at=datetime.now(timezone.utc),
        payload_hash="a" * 64,
        title="Berserk",
        alternate_titles=(),
        description=None,
        publication_year=1989,
        media_type="Manga",
        external_average_rating=None,
        external_rating_votes=None,
        cover_image_url=cover_image_url,
        genres=(),
        tags=(),
        demographics=(),
        creator_credits=(),
    )


def _image() -> DownloadedCoverImage:
    return DownloadedCoverImage(
        content=b"\x89PNG\r\n\x1a\ncover",
        content_type="image/png",
        extension="png",
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


@pytest.mark.asyncio
async def test_series_ingestion_stores_cover_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    payload = {"series_id": 42}
    record = _record()
    client = MagicMock()
    client.get_series = AsyncMock(return_value=payload)
    client.get_cover_image = AsyncMock(return_value=_image())
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock(
        return_value=(
            "https://mangarecon.com/covers/mangaupdates/42/hash.png"
        )
    )
    expected = service.MangaIngestionResult(
        manga_id=17,
        created=True,
        changed=True,
        cover_status="stored",
    )
    persist = AsyncMock(return_value=expected)

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: record,
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    result = await service.ingest_mangaupdates_series(
        user_db,
        client=client,
        series_id=42,
        cover_store=cover_store,
    )

    assert result == expected
    client.get_series.assert_awaited_once_with(42)
    client.get_cover_image.assert_awaited_once_with(
        record.cover_image_url
    )
    cover_store.store_cover.assert_awaited_once_with(
        provider_key="mangaupdates",
        external_id="42",
        image=_image(),
    )
    stored_record = persist.await_args.kwargs["record"]
    assert stored_record.cover_image_url == (
        "https://mangarecon.com/covers/mangaupdates/42/hash.png"
    )
    assert persist.await_args.kwargs["cover_status"] == "stored"


@pytest.mark.asyncio
async def test_explicit_series_is_rejected_before_cover_download_or_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_db = MagicMock()
    user_db.commit = AsyncMock()
    record = replace(_record(), genres=("Action", "Hentai"))
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock()
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock()
    upsert = AsyncMock()

    monkeypatch.setattr(service, "parse_mangaupdates_series", lambda payload: record)
    monkeypatch.setattr(service, "upsert_catalog_manga", upsert)

    with pytest.raises(CatalogContentExcluded):
        await service.ingest_mangaupdates_series(
            user_db, client=client, series_id=42, cover_store=cover_store
        )

    client.get_cover_image.assert_not_awaited()
    cover_store.store_cover.assert_not_awaited()
    upsert.assert_not_awaited()
    user_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cover_transport_failure_preserves_existing_cover(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    record = _record()
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock(
        side_effect=MangaUpdatesTransportError("CDN unavailable")
    )
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock()
    expected = service.MangaIngestionResult(
        manga_id=17,
        created=False,
        changed=False,
        cover_status="failed",
    )
    persist = AsyncMock(return_value=expected)

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: record,
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    result = await service.ingest_mangaupdates_series(
        MagicMock(),
        client=client,
        series_id=42,
        cover_store=cover_store,
    )

    assert result == expected
    assert persist.await_args.kwargs["record"].cover_image_url is None
    assert persist.await_args.kwargs["cover_status"] == "failed"
    cover_store.store_cover.assert_not_awaited()
    assert "existing stored cover will be preserved" in caplog.text


@pytest.mark.asyncio
async def test_missing_source_cover_skips_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(cover_image_url=None)
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock()
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock()
    persist = AsyncMock(
        return_value=service.MangaIngestionResult(
            manga_id=17,
            created=True,
            changed=True,
            cover_status="source_missing",
        )
    )

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: record,
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    await service.ingest_mangaupdates_series(
        MagicMock(),
        client=client,
        series_id=42,
        cover_store=cover_store,
    )

    client.get_cover_image.assert_not_awaited()
    cover_store.store_cover.assert_not_awaited()
    assert persist.await_args.kwargs["cover_status"] == (
        "source_missing"
    )


@pytest.mark.asyncio
async def test_missing_cover_response_is_classified_as_source_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record()
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock(
        side_effect=MangaUpdatesHTTPError(
            "cover missing",
            status_code=404,
        )
    )
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock()
    persist = AsyncMock(
        return_value=service.MangaIngestionResult(
            manga_id=17,
            created=True,
            changed=True,
            cover_status="source_missing",
        )
    )

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: record,
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    result = await service.ingest_mangaupdates_series(
        MagicMock(),
        client=client,
        series_id=42,
        cover_store=cover_store,
    )

    assert result.cover_status == "source_missing"
    assert persist.await_args.kwargs["record"].cover_image_url is None
    assert persist.await_args.kwargs["cover_status"] == (
        "source_missing"
    )
    cover_store.store_cover.assert_not_awaited()


@pytest.mark.asyncio
async def test_cover_rate_limit_stops_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock(
        side_effect=MangaUpdatesRateLimitError(retry_after="30")
    )
    persist = AsyncMock()

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: _record(),
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    with pytest.raises(MangaUpdatesRateLimitError):
        await service.ingest_mangaupdates_series(
            MagicMock(),
            client=client,
            series_id=42,
            cover_store=MagicMock(),
        )

    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_cover_storage_failure_stops_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.get_series = AsyncMock(return_value={"series_id": 42})
    client.get_cover_image = AsyncMock(return_value=_image())
    cover_store = MagicMock()
    cover_store.store_cover = AsyncMock(
        side_effect=CoverStorageError("S3 unavailable")
    )
    persist = AsyncMock()

    monkeypatch.setattr(
        service,
        "parse_mangaupdates_series",
        lambda value: _record(),
    )
    monkeypatch.setattr(
        service,
        "_ingest_mangaupdates_record",
        persist,
    )

    with pytest.raises(CoverStorageError, match="S3 unavailable"):
        await service.ingest_mangaupdates_series(
            MagicMock(),
            client=client,
            series_id=42,
            cover_store=cover_store,
        )

    persist.assert_not_awaited()
