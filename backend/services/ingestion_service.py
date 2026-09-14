from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal

from backend.clients.mangaupdates_client import (
    MangaUpdatesClient,
    MangaUpdatesClientError,
    MangaUpdatesRateLimitError,
)
from backend.db.client_db import ClientWriteDatabase
from backend.ingestion.mangaupdates_parser import (
    parse_mangaupdates_series,
)
from backend.ingestion.records import MangaIngestionRecord
from backend.repositories.ingestion_repo import upsert_catalog_manga
from backend.storage.cover_store import (
    CoverStore,
)


_MANGAUPDATES_DISPLAY_NAME = "MangaUpdates"
_MANGAUPDATES_ATTRIBUTION_URL = (
    "https://www.mangaupdates.com/"
)

logger = logging.getLogger(__name__)

CoverIngestionStatus = Literal[
    "not_configured",
    "source_missing",
    "stored",
    "failed",
]


@dataclass(frozen=True, slots=True)
class MangaIngestionResult:
    manga_id: int
    created: bool
    changed: bool
    cover_status: CoverIngestionStatus = "not_configured"


async def _ingest_mangaupdates_record(
    user_db: ClientWriteDatabase,
    *,
    record: MangaIngestionRecord,
    cover_status: CoverIngestionStatus,
) -> MangaIngestionResult:
    """Atomically persist one already-normalized MangaUpdates record."""
    try:
        outcome = await upsert_catalog_manga(
            user_db,
            record=record,
            provider_display_name=(
                _MANGAUPDATES_DISPLAY_NAME
            ),
            provider_attribution_url=(
                _MANGAUPDATES_ATTRIBUTION_URL
            ),
        )

        if outcome.changed:
            await user_db.commit()

        manga_id = outcome.manga.manga_id

        if manga_id is None:
            raise RuntimeError(
                "Ingested manga has no database ID."
            )
    except Exception:
        await user_db.rollback()
        raise

    return MangaIngestionResult(
        manga_id=manga_id,
        created=outcome.created,
        changed=outcome.changed,
        cover_status=cover_status,
    )


async def ingest_mangaupdates_payload(
    user_db: ClientWriteDatabase,
    *,
    payload: Mapping[str, Any],
) -> MangaIngestionResult:
    """
    Parse and atomically persist one MangaUpdates series payload.
    """
    record = parse_mangaupdates_series(payload)
    return await _ingest_mangaupdates_record(
        user_db,
        record=record,
        cover_status="not_configured",
    )


async def _store_record_cover(
    record: MangaIngestionRecord,
    *,
    client: MangaUpdatesClient,
    cover_store: CoverStore | None,
) -> tuple[MangaIngestionRecord, CoverIngestionStatus]:
    if cover_store is None:
        return record, "not_configured"

    if record.cover_image_url is None:
        return record, "source_missing"

    try:
        image = await client.get_cover_image(
            record.cover_image_url
        )
        stored_url = await cover_store.store_cover(
            provider_key=record.provider_key,
            external_id=record.external_id,
            image=image,
        )
    except MangaUpdatesRateLimitError:
        raise
    except MangaUpdatesClientError as exc:
        logger.warning(
            (
                "Cover caching failed for MangaUpdates series %s; "
                "existing stored cover will be preserved: %s"
            ),
            record.external_id,
            exc,
        )
        return replace(record, cover_image_url=None), "failed"

    return replace(record, cover_image_url=stored_url), "stored"

async def ingest_mangaupdates_series(
    user_db: ClientWriteDatabase,
    *,
    client: MangaUpdatesClient,
    series_id: int,
    cover_store: CoverStore | None = None,
) -> MangaIngestionResult:
    """
    Fetch and atomically persist one MangaUpdates series.
    """
    payload = await client.get_series(series_id)

    if cover_store is None:
        return await ingest_mangaupdates_payload(
            user_db,
            payload=payload,
        )

    record = parse_mangaupdates_series(payload)
    record, cover_status = await _store_record_cover(
        record,
        client=client,
        cover_store=cover_store,
    )

    return await _ingest_mangaupdates_record(
        user_db,
        record=record,
        cover_status=cover_status,
    )
