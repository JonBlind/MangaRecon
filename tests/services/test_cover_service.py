from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.ingestion.images import DownloadedCoverImage
from backend.repositories.ingestion_repo import CatalogCoverCandidate
from backend.services import cover_service


def _candidate() -> CatalogCoverCandidate:
    return CatalogCoverCandidate(
        manga_id=7,
        external_id="42",
        source_url=(
            "https://cdn.mangaupdates.com/image/i42.png"
        ),
    )


def _image() -> DownloadedCoverImage:
    return DownloadedCoverImage(
        content=b"\x89PNG\r\n\x1a\ncover",
        content_type="image/png",
        extension="png",
    )


@pytest.mark.asyncio
async def test_cache_catalog_cover_stores_updates_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = MagicMock()
    database.commit = AsyncMock()
    database.rollback = AsyncMock()
    client = MagicMock()
    client.get_cover_image = AsyncMock(return_value=_image())
    store = MagicMock()
    store.store_cover = AsyncMock(
        return_value=(
            "https://mangarecon.com/covers/mangaupdates/42/hash.png"
        )
    )
    replace_url = AsyncMock(return_value=True)
    monkeypatch.setattr(
        cover_service,
        "replace_catalog_cover_url",
        replace_url,
    )

    result = await cover_service.cache_catalog_cover(
        database,
        candidate=_candidate(),
        client=client,
        cover_store=store,
    )

    assert result == cover_service.CoverCacheResult(
        manga_id=7,
        external_id="42",
        stored_url=(
            "https://mangarecon.com/covers/mangaupdates/42/hash.png"
        ),
        database_updated=True,
    )
    client.get_cover_image.assert_awaited_once_with(
        _candidate().source_url
    )
    store.store_cover.assert_awaited_once_with(
        provider_key="mangaupdates",
        external_id="42",
        image=_image(),
    )
    replace_url.assert_awaited_once_with(
        database,
        manga_id=7,
        expected_source_url=_candidate().source_url,
        stored_url=(
            "https://mangarecon.com/covers/mangaupdates/42/hash.png"
        ),
    )
    database.commit.assert_awaited_once_with()
    database.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_cache_catalog_cover_rolls_back_concurrent_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = MagicMock()
    database.commit = AsyncMock()
    database.rollback = AsyncMock()
    client = MagicMock()
    client.get_cover_image = AsyncMock(return_value=_image())
    store = MagicMock()
    store.store_cover = AsyncMock(return_value="https://stored.example")
    monkeypatch.setattr(
        cover_service,
        "replace_catalog_cover_url",
        AsyncMock(return_value=False),
    )

    result = await cover_service.cache_catalog_cover(
        database,
        candidate=_candidate(),
        client=client,
        cover_store=store,
    )

    assert result.database_updated is False
    database.commit.assert_not_awaited()
    database.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cache_catalog_cover_rolls_back_database_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = MagicMock()
    database.commit = AsyncMock()
    database.rollback = AsyncMock()
    client = MagicMock()
    client.get_cover_image = AsyncMock(return_value=_image())
    store = MagicMock()
    store.store_cover = AsyncMock(return_value="https://stored.example")
    monkeypatch.setattr(
        cover_service,
        "replace_catalog_cover_url",
        AsyncMock(side_effect=RuntimeError("database failed")),
    )

    with pytest.raises(RuntimeError, match="database failed"):
        await cover_service.cache_catalog_cover(
            database,
            candidate=_candidate(),
            client=client,
            cover_store=store,
        )

    database.commit.assert_not_awaited()
    database.rollback.assert_awaited_once_with()
