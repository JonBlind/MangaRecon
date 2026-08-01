from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from backend.db.client_db import ClientWriteDatabase
from backend.ingestion.mangaupdates_parser import parse_mangaupdates_series
from backend.repositories.ingestion_repo import upsert_catalog_manga
from backend.clients.mangaupdates_client import MangaUpdatesClient


_MANGAUPDATES_DISPLAY_NAME = "MangaUpdates"
_MANGAUPDATES_ATTRIBUTION_URL = (
    "https://www.mangaupdates.com/"
)


@dataclass(frozen=True, slots=True)
class MangaIngestionResult:
    manga_id: int
    created: bool
    changed: bool


async def ingest_mangaupdates_payload(
    user_db: ClientWriteDatabase,
    *,
    payload: Mapping[str, Any],
) -> MangaIngestionResult:
    """
    Parse and atomically persist one MangaUpdates series payload.
    """
    record = parse_mangaupdates_series(payload)

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
    )

async def ingest_mangaupdates_series(
    user_db: ClientWriteDatabase,
    *,
    client: MangaUpdatesClient,
    series_id: int,
) -> MangaIngestionResult:
    """
    Fetch and atomically persist one MangaUpdates series.
    """
    payload = await client.get_series(series_id)

    return await ingest_mangaupdates_payload(
        user_db,
        payload=payload,
    )