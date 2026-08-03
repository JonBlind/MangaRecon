from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal


CreatorRole = Literal["author", "artist"]


@dataclass(frozen=True, slots=True)
class CreatorCreditRecord:
    """
    Source-neutral creator credit from an external provider.
    """

    provider_key: str
    external_id: str | None
    name: str
    role: CreatorRole
    source_url: str | None


@dataclass(frozen=True, slots=True)
class MangaIngestionRecord:
    """
    Normalized manga metadata ready for later database upserting.
    """

    provider_key: str
    external_id: str
    source_url: str
    source_updated_at: datetime | None
    payload_hash: str

    title: str
    alternate_titles: tuple[str, ...]
    description: str | None
    publication_year: int | None
    media_type: str | None

    external_average_rating: Decimal | None
    external_rating_votes: int | None
    cover_image_url: str | None

    genres: tuple[str, ...]
    tags: tuple[str, ...]
    demographics: tuple[str, ...]
    creator_credits: tuple[CreatorCreditRecord, ...]
