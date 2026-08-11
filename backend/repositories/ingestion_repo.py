from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)
from backend.db.models.creator import Creator
from backend.db.models.creator_external_source import CreatorExternalSource
from backend.db.models.data_provider import DataProvider
from backend.db.models.demographics import Demographic
from backend.db.models.genre import Genre
from backend.db.models.manga import Manga
from backend.db.models.manga_alternate_title import MangaAlternateTitle
from backend.db.models.manga_creator import MangaCreator
from backend.db.models.manga_external_source import MangaExternalSource
from backend.db.models.tag import Tag
from backend.ingestion.records import (
    CreatorCreditRecord,
    MangaIngestionRecord,
)


_EntityT = TypeVar("_EntityT")

_EXTERNAL_ID_LOOKUP_BATCH_SIZE = 5_000


@dataclass(frozen=True, slots=True)
class CatalogUpsertOutcome:
    """
    Internal repository result.

    The service commits the transaction before exposing the manga ID.
    """

    manga: Manga
    created: bool
    changed: bool


async def find_existing_catalog_external_ids(
    user_db: ClientReadDatabase,
    *,
    provider_key: str,
    external_ids: Sequence[str],
) -> set[str]:
    """
    Return provider external IDs already present in the catalog.

    Large input sets are queried in bounded batches so PostgreSQL is never
    asked to bind an unbounded number of values in one statement.
    """
    requested_ids = tuple(dict.fromkeys(external_ids))

    if not requested_ids:
        return set()

    existing_ids: set[str] = set()

    for offset in range(
        0,
        len(requested_ids),
        _EXTERNAL_ID_LOOKUP_BATCH_SIZE,
    ):
        batch = requested_ids[
            offset : offset + _EXTERNAL_ID_LOOKUP_BATCH_SIZE
        ]
        stmt = (
            select(MangaExternalSource.external_id)
            .join(
                DataProvider,
                DataProvider.provider_id
                == MangaExternalSource.provider_id,
            )
            .where(
                DataProvider.provider_key == provider_key,
                MangaExternalSource.external_id.in_(batch),
            )
        )
        existing_ids.update(
            await user_db.scalars_all(stmt)
        )

    return existing_ids


async def upsert_catalog_manga(
    user_db: ClientWriteDatabase,
    *,
    record: MangaIngestionRecord,
    provider_display_name: str,
    provider_attribution_url: str,
) -> CatalogUpsertOutcome:
    """
    Create or update one canonical catalog manga.

    A manga is identified only by its provider and external ID. Titles are
    never used to merge records.

    This function does not commit or roll back. The calling service owns the
    transaction.
    """
    provider = await _get_or_create_provider(
        user_db,
        provider_key=record.provider_key,
        display_name=provider_display_name,
        attribution_url=provider_attribution_url,
    )

    source = await _find_manga_source(
        user_db,
        provider=provider,
        external_id=record.external_id,
    )

    if (
        source is not None
        and source.payload_hash == record.payload_hash
    ):
        manga = await user_db.get(
            Manga,
            source.manga_id,
        )

        if manga is None:
            raise RuntimeError(
                "Manga external source references a missing manga."
            )

        return CatalogUpsertOutcome(
            manga=manga,
            created=False,
            changed=False,
        )

    if source is None:
        manga = Manga(title=record.title)

        # Mark canonical relationship collections as loaded before any
        # metadata lookup can autoflush.
        manga.alternate_titles = []
        manga.genres = []
        manga.tags = []
        manga.demographics = []
        manga.creator_links = []

        user_db.add(manga)

        source = MangaExternalSource(
            manga=manga,
            provider=provider,
            external_id=record.external_id,
            source_url=record.source_url,
            source_updated_at=record.source_updated_at,
            payload_hash=record.payload_hash,
        )
        user_db.add(source)
        created = True
    else:
        manga = await _load_manga_for_replacement(
            user_db,
            manga_id=source.manga_id,
        )
        created = False

        source.source_url = record.source_url
        source.source_updated_at = record.source_updated_at
        source.payload_hash = record.payload_hash
        source.fetched_at = datetime.now(timezone.utc)

    await _replace_canonical_metadata(
        user_db,
        manga=manga,
        provider=provider,
        record=record,
    )

    return CatalogUpsertOutcome(
        manga=manga,
        created=created,
        changed=True,
    )


async def _get_or_create_provider(
    user_db: ClientWriteDatabase,
    *,
    provider_key: str,
    display_name: str,
    attribution_url: str,
) -> DataProvider:
    stmt = select(DataProvider).where(
        DataProvider.provider_key == provider_key
    )
    provider = await user_db.scalar_one_or_none(stmt)

    if provider is not None:
        return provider

    provider = DataProvider(
        provider_key=provider_key,
        display_name=display_name,
        attribution_url=attribution_url,
    )
    user_db.add(provider)
    return provider


async def _find_manga_source(
    user_db: ClientWriteDatabase,
    *,
    provider: DataProvider,
    external_id: str,
) -> MangaExternalSource | None:
    if provider.provider_id is None:
        return None

    stmt = select(MangaExternalSource).where(
        MangaExternalSource.provider_id
        == provider.provider_id,
        MangaExternalSource.external_id
        == external_id,
    )
    return await user_db.scalar_one_or_none(stmt)


async def _load_manga_for_replacement(
    user_db: ClientWriteDatabase,
    *,
    manga_id: int,
) -> Manga:
    stmt = (
        select(Manga)
        .options(
            selectinload(Manga.alternate_titles),
            selectinload(Manga.genres),
            selectinload(Manga.tags),
            selectinload(Manga.demographics),
            selectinload(
                Manga.creator_links
            ).selectinload(
                MangaCreator.creator
            ),
        )
        .where(Manga.manga_id == manga_id)
    )
    manga = await user_db.scalar_one_or_none(stmt)

    if manga is None:
        raise RuntimeError(
            "Manga external source references a missing manga."
        )

    return manga


async def _replace_canonical_metadata(
    user_db: ClientWriteDatabase,
    *,
    manga: Manga,
    provider: DataProvider,
    record: MangaIngestionRecord,
) -> None:
    manga.title = record.title
    manga.description = record.description
    manga.publication_year = record.publication_year
    manga.media_type = record.media_type
    manga.external_average_rating = (
        record.external_average_rating
    )
    manga.external_rating_votes = (
        record.external_rating_votes
    )
    manga.cover_image_url = record.cover_image_url

    existing_titles = {
        alternate.title: alternate
        for alternate in manga.alternate_titles
    }
    manga.alternate_titles = [
        existing_titles.get(title)
        or MangaAlternateTitle(title=title)
        for title in record.alternate_titles
    ]

    manga.genres = await _resolve_named_entities(
        user_db,
        names=record.genres,
        model=Genre,
        name_column=Genre.genre_name,
    )
    manga.tags = await _resolve_named_entities(
        user_db,
        names=record.tags,
        model=Tag,
        name_column=Tag.tag_name,
    )
    manga.demographics = await _resolve_named_entities(
        user_db,
        names=record.demographics,
        model=Demographic,
        name_column=Demographic.demographic_name,
    )
    manga.creator_links = await _resolve_creator_links(
        user_db,
        manga=manga,
        provider=provider,
        credits=record.creator_credits,
    )


async def _resolve_named_entities(
    user_db: ClientWriteDatabase,
    *,
    names: tuple[str, ...],
    model: type[_EntityT],
    name_column: Any,
) -> list[_EntityT]:
    if not names:
        return []

    normalized_names = tuple(
        name.casefold()
        for name in names
    )
    stmt = select(model).where(
        func.lower(name_column).in_(normalized_names)
    )
    existing_entities = await user_db.scalars_all(stmt)

    entities_by_name = {
        getattr(entity, name_column.key).casefold(): entity
        for entity in existing_entities
    }

    resolved = []

    for name in names:
        identity = name.casefold()
        entity = entities_by_name.get(identity)

        if entity is None:
            entity = model(
                **{
                    name_column.key: name,
                }
            )
            user_db.add(entity)
            entities_by_name[identity] = entity

        resolved.append(entity)

    return resolved


async def _resolve_creator_links(
    user_db: ClientWriteDatabase,
    *,
    manga: Manga,
    provider: DataProvider,
    credits: tuple[CreatorCreditRecord, ...],
) -> list[MangaCreator]:
    if not credits:
        return []

    first_credit_by_external_id: dict[
        str,
        CreatorCreditRecord,
    ] = {}

    for credit in credits:
        if credit.external_id is None:
            continue

        first_credit_by_external_id.setdefault(
            credit.external_id,
            credit,
        )

    external_ids = tuple(
        first_credit_by_external_id
    )

    if (
        provider.provider_id is None
        or not external_ids
    ):
        existing_sources = []
    else:
        stmt = (
            select(CreatorExternalSource)
            .options(
                selectinload(
                    CreatorExternalSource.creator
                )
            )
            .where(
                CreatorExternalSource.provider_id
                == provider.provider_id,
                CreatorExternalSource.external_id.in_(
                    external_ids
                ),
            )
        )
        existing_sources = await user_db.scalars_all(
            stmt
        )

    sources_by_external_id = {
        source.external_id: source
        for source in existing_sources
    }
    creators_by_external_id = {}
    fetched_at = datetime.now(timezone.utc)

    for external_id, credit in (
        first_credit_by_external_id.items()
    ):
        source = sources_by_external_id.get(
            external_id
        )

        if source is None:
            creator = Creator(
                creator_name=credit.name
            )
            source = CreatorExternalSource(
                creator=creator,
                provider=provider,
                external_id=external_id,
                source_url=credit.source_url,
            )
            user_db.add(creator)
            user_db.add(source)
        else:
            creator = source.creator
            creator.creator_name = credit.name
            source.source_url = credit.source_url
            source.fetched_at = fetched_at

        creators_by_external_id[external_id] = (
            creator
        )

    existing_links = {
        (link.creator_id, link.role): link
        for link in manga.creator_links
    }
    existing_links_by_name_and_role = {
        (
            link.creator.creator_name.casefold(),
            link.role,
        ): link
        for link in manga.creator_links
    }
    idless_creators_by_name: dict[str, Creator] = {}
    resolved_links = []

    for credit in credits:
        if credit.external_id is None:
            name_identity = credit.name.casefold()
            existing_link = (
                existing_links_by_name_and_role.get(
                    (
                        name_identity,
                        credit.role,
                    )
                )
            )

            if existing_link is not None:
                resolved_links.append(existing_link)
                idless_creators_by_name.setdefault(
                    name_identity,
                    existing_link.creator,
                )
                continue

            creator = idless_creators_by_name.get(
                name_identity
            )

            if creator is None:
                creator = Creator(
                    creator_name=credit.name
                )
                user_db.add(creator)
                idless_creators_by_name[
                    name_identity
                ] = creator
        else:
            creator = creators_by_external_id[
                credit.external_id
            ]

        existing_link = None

        if creator.creator_id is not None:
            existing_link = existing_links.get(
                (
                    creator.creator_id,
                    credit.role,
                )
            )

        if existing_link is not None:
            resolved_links.append(existing_link)
        else:
            resolved_links.append(
                MangaCreator(
                    creator=creator,
                    role=credit.role,
                )
            )

    return resolved_links
