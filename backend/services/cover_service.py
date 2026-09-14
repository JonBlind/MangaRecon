from __future__ import annotations

from dataclasses import dataclass

from backend.clients.mangaupdates_client import MangaUpdatesClient
from backend.db.client_db import ClientWriteDatabase
from backend.repositories.ingestion_repo import (
    CatalogCoverCandidate,
    replace_catalog_cover_url,
)
from backend.storage.cover_store import CoverStore


@dataclass(frozen=True, slots=True)
class CoverCacheResult:
    """Result of durably caching one existing catalog cover."""

    manga_id: int
    external_id: str
    stored_url: str
    database_updated: bool


async def cache_catalog_cover(
    user_db: ClientWriteDatabase,
    *,
    candidate: CatalogCoverCandidate,
    client: MangaUpdatesClient,
    cover_store: CoverStore,
) -> CoverCacheResult:
    """Download, store, and conditionally repoint one catalog cover."""
    image = await client.get_cover_image(candidate.source_url)
    stored_url = await cover_store.store_cover(
        provider_key="mangaupdates",
        external_id=candidate.external_id,
        image=image,
    )

    try:
        database_updated = await replace_catalog_cover_url(
            user_db,
            manga_id=candidate.manga_id,
            expected_source_url=candidate.source_url,
            stored_url=stored_url,
        )

        if database_updated:
            await user_db.commit()
        else:
            await user_db.rollback()
    except Exception:
        await user_db.rollback()
        raise

    return CoverCacheResult(
        manga_id=candidate.manga_id,
        external_id=candidate.external_id,
        stored_url=stored_url,
        database_updated=database_updated,
    )
