from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import Engine, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, selectinload

import backend.repositories.ingestion_repo as repository
from backend.db.client_db import ClientWriteDatabase
from backend.db.models.collection import Collection
from backend.db.models.creator import Creator
from backend.db.models.creator_external_source import (
    CreatorExternalSource,
)
from backend.db.models.data_provider import DataProvider
from backend.db.models.demographics import Demographic
from backend.db.models.genre import Genre
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection
from backend.db.models.manga_creator import MangaCreator
from backend.db.models.manga_external_source import (
    MangaExternalSource,
)
from backend.db.models.rating import Rating
from backend.db.models.tag import Tag
from backend.db.models.user import User
from backend.ingestion.records import (
    CreatorCreditRecord,
    MangaIngestionRecord,
)


@pytest_asyncio.fixture
async def ingestion_db(
    database_urls: dict[str, str],
) -> AsyncIterator[ClientWriteDatabase]:
    engine = create_async_engine(
        database_urls["manga_write"],
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with session_factory() as session:
            yield ClientWriteDatabase(session)
    finally:
        await engine.dispose()


def make_record(
    **changes: object,
) -> MangaIngestionRecord:
    values: dict[str, object] = {
        "provider_key": "mangaupdates",
        "external_id": "100",
        "source_url": (
            "https://www.mangaupdates.com/"
            "series/example"
        ),
        "source_updated_at": datetime(
            2026,
            7,
            21,
            tzinfo=timezone.utc,
        ),
        "payload_hash": "a" * 64,
        "title": "Example Manga",
        "alternate_titles": (
            "Example Alternate",
            "Example Japanese",
        ),
        "description": "Original description.",
        "publication_year": 2001,
        "media_type": "Manga",
        "external_average_rating": Decimal("8.50"),
        "external_rating_votes": 100,
        "cover_image_url": (
            "https://example.com/cover.jpg"
        ),
        "genres": (
            "Action",
            "Fantasy",
        ),
        "tags": (
            "Dark Fantasy",
            "Adventure",
        ),
        "demographics": (
            "Seinen",
        ),
        "creator_credits": (
            CreatorCreditRecord(
                provider_key="mangaupdates",
                external_id="10",
                name="Creator One",
                role="author",
                source_url=(
                    "https://example.com/creators/10"
                ),
            ),
            CreatorCreditRecord(
                provider_key="mangaupdates",
                external_id="10",
                name="Creator One",
                role="artist",
                source_url=(
                    "https://example.com/creators/10"
                ),
            ),
            CreatorCreditRecord(
                provider_key="mangaupdates",
                external_id="20",
                name="Creator Two",
                role="artist",
                source_url=(
                    "https://example.com/creators/20"
                ),
            ),
        ),
    }
    values.update(changes)

    return MangaIngestionRecord(**values)  # type: ignore[arg-type]


async def upsert_and_commit(
    user_db: ClientWriteDatabase,
    record: MangaIngestionRecord,
    *,
    display_name: str = "MangaUpdates",
    attribution_url: str = (
        "https://www.mangaupdates.com/"
    ),
):
    outcome = await repository.upsert_catalog_manga(
        user_db,
        record=record,
        provider_display_name=display_name,
        provider_attribution_url=attribution_url,
    )
    await user_db.commit()
    return outcome


async def load_manga(
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

    assert manga is not None
    return manga


@pytest.mark.asyncio
async def test_initial_upsert_creates_complete_catalog_graph(
    ingestion_db: ClientWriteDatabase,
) -> None:
    outcome = await upsert_and_commit(
        ingestion_db,
        make_record(),
    )

    assert outcome.created is True
    assert outcome.changed is True
    assert outcome.manga.manga_id is not None

    manga = await load_manga(
        ingestion_db,
        manga_id=outcome.manga.manga_id,
    )

    assert manga.title == "Example Manga"
    assert manga.description == "Original description."
    assert manga.publication_year == 2001
    assert manga.media_type == "Manga"
    assert manga.external_average_rating == Decimal("8.50")
    assert manga.external_rating_votes == 100
    assert manga.cover_image_url == (
        "https://example.com/cover.jpg"
    )

    assert {
        alternate.title
        for alternate in manga.alternate_titles
    } == {
        "Example Alternate",
        "Example Japanese",
    }
    assert {
        genre.genre_name
        for genre in manga.genres
    } == {
        "Action",
        "Fantasy",
    }
    assert {
        tag.tag_name
        for tag in manga.tags
    } == {
        "Dark Fantasy",
        "Adventure",
    }
    assert {
        demographic.demographic_name
        for demographic in manga.demographics
    } == {
        "Seinen",
    }
    assert {
        (
            link.creator.creator_name,
            link.role,
        )
        for link in manga.creator_links
    } == {
        ("Creator One", "author"),
        ("Creator One", "artist"),
        ("Creator Two", "artist"),
    }

    provider = await ingestion_db.scalar_one_or_none(
        select(DataProvider).where(
            DataProvider.provider_key
            == "mangaupdates"
        )
    )
    assert provider is not None
    assert provider.display_name == "MangaUpdates"
    assert provider.attribution_url == (
        "https://www.mangaupdates.com/"
    )

    source = await ingestion_db.scalar_one_or_none(
        select(MangaExternalSource).where(
            MangaExternalSource.provider_id
            == provider.provider_id,
            MangaExternalSource.external_id
            == "100",
        )
    )
    assert source is not None
    assert source.manga_id == manga.manga_id
    assert source.payload_hash == "a" * 64

    creator_sources = await ingestion_db.scalars_all(
        select(CreatorExternalSource)
        .options(
            selectinload(
                CreatorExternalSource.creator
            )
        )
        .where(
            CreatorExternalSource.provider_id
            == provider.provider_id
        )
    )

    assert {
        (
            source.external_id,
            source.creator.creator_name,
        )
        for source in creator_sources
    } == {
        ("10", "Creator One"),
        ("20", "Creator Two"),
    }


@pytest.mark.asyncio
async def test_existing_external_id_lookup_returns_only_provider_matches(
    ingestion_db: ClientWriteDatabase,
) -> None:
    await upsert_and_commit(
        ingestion_db,
        make_record(external_id="100"),
    )
    await upsert_and_commit(
        ingestion_db,
        make_record(
            external_id="300",
            payload_hash="b" * 64,
            title="Another Manga",
        ),
    )

    result = await repository.find_existing_catalog_external_ids(
        ingestion_db,
        provider_key="mangaupdates",
        external_ids=("100", "200", "300"),
    )

    assert result == {"100", "300"}


@pytest.mark.asyncio
async def test_same_payload_hash_is_idempotent(
    ingestion_db: ClientWriteDatabase,
) -> None:
    record = make_record()
    initial = await upsert_and_commit(
        ingestion_db,
        record,
    )

    source = await ingestion_db.scalar_one_or_none(
        select(MangaExternalSource).where(
            MangaExternalSource.manga_id
            == initial.manga.manga_id
        )
    )
    assert source is not None
    original_fetched_at = source.fetched_at

    repeated = await repository.upsert_catalog_manga(
        ingestion_db,
        record=record,
        provider_display_name="MangaUpdates",
        provider_attribution_url=(
            "https://www.mangaupdates.com/"
        ),
    )

    assert repeated.manga.manga_id == (
        initial.manga.manga_id
    )
    assert repeated.created is False
    assert repeated.changed is False

    source = await ingestion_db.scalar_one_or_none(
        select(MangaExternalSource).where(
            MangaExternalSource.manga_id
            == initial.manga.manga_id
        )
    )
    assert source is not None
    assert source.fetched_at == original_fetched_at


@pytest.mark.asyncio
async def test_changed_payload_replaces_canonical_metadata(
    ingestion_db: ClientWriteDatabase,
) -> None:
    initial = await upsert_and_commit(
        ingestion_db,
        make_record(
            alternate_titles=(
                "Removed Alternate",
                "Retained Alternate",
            ),
        ),
    )
    manga_id = initial.manga.manga_id
    assert manga_id is not None

    updated_record = make_record(
        payload_hash="b" * 64,
        source_url=(
            "https://www.mangaupdates.com/"
            "series/updated"
        ),
        title="Updated Manga",
        alternate_titles=(
            "Retained Alternate",
            "New Alternate",
        ),
        description="Updated description.",
        publication_year=2002,
        external_average_rating=Decimal("9.10"),
        external_rating_votes=250,
        genres=(
            "Fantasy",
            "Drama",
        ),
        tags=(
            "Adventure",
            "Tragedy",
        ),
        demographics=(
            "Shounen",
        ),
        creator_credits=(
            CreatorCreditRecord(
                provider_key="mangaupdates",
                external_id="10",
                name="Creator One Updated",
                role="author",
                source_url=(
                    "https://example.com/"
                    "creators/10-updated"
                ),
            ),
            CreatorCreditRecord(
                provider_key="mangaupdates",
                external_id="30",
                name="Creator Three",
                role="artist",
                source_url=(
                    "https://example.com/creators/30"
                ),
            ),
        ),
    )

    outcome = await upsert_and_commit(
        ingestion_db,
        updated_record,
    )

    assert outcome.manga.manga_id == manga_id
    assert outcome.created is False
    assert outcome.changed is True

    manga = await load_manga(
        ingestion_db,
        manga_id=manga_id,
    )

    assert manga.title == "Updated Manga"
    assert manga.description == "Updated description."
    assert manga.publication_year == 2002
    assert manga.external_average_rating == Decimal("9.10")
    assert manga.external_rating_votes == 250

    assert {
        alternate.title
        for alternate in manga.alternate_titles
    } == {
        "Retained Alternate",
        "New Alternate",
    }
    assert {
        genre.genre_name
        for genre in manga.genres
    } == {
        "Fantasy",
        "Drama",
    }
    assert {
        tag.tag_name
        for tag in manga.tags
    } == {
        "Adventure",
        "Tragedy",
    }
    assert {
        demographic.demographic_name
        for demographic in manga.demographics
    } == {
        "Shounen",
    }
    assert {
        (
            link.creator.creator_name,
            link.role,
        )
        for link in manga.creator_links
    } == {
        ("Creator One Updated", "author"),
        ("Creator Three", "artist"),
    }

    source = await ingestion_db.scalar_one_or_none(
        select(MangaExternalSource).where(
            MangaExternalSource.manga_id == manga_id
        )
    )
    assert source is not None
    assert source.payload_hash == "b" * 64
    assert source.source_url.endswith("/series/updated")


@pytest.mark.asyncio
async def test_named_metadata_is_reused_case_insensitively(
    ingestion_db: ClientWriteDatabase,
) -> None:
    genre = Genre(genre_name="Action")
    tag = Tag(tag_name="Dark Fantasy")
    demographic = Demographic(
        demographic_name="Seinen"
    )

    ingestion_db.add(genre)
    ingestion_db.add(tag)
    ingestion_db.add(demographic)
    await ingestion_db.commit()

    genre_id = genre.genre_id
    tag_id = tag.tag_id
    demographic_id = demographic.demographic_id

    outcome = await upsert_and_commit(
        ingestion_db,
        make_record(
            genres=("action",),
            tags=("DARK FANTASY",),
            demographics=("seinen",),
            creator_credits=(),
        ),
    )
    assert outcome.manga.manga_id is not None

    manga = await load_manga(
        ingestion_db,
        manga_id=outcome.manga.manga_id,
    )

    assert [
        item.genre_id
        for item in manga.genres
    ] == [genre_id]
    assert [
        item.tag_id
        for item in manga.tags
    ] == [tag_id]
    assert [
        item.demographic_id
        for item in manga.demographics
    ] == [demographic_id]

    assert manga.genres[0].genre_name == "Action"
    assert manga.tags[0].tag_name == "Dark Fantasy"
    assert (
        manga.demographics[0].demographic_name
        == "Seinen"
    )


@pytest.mark.asyncio
async def test_idless_creator_is_preserved_and_reused_on_refresh(
    ingestion_db: ClientWriteDatabase,
) -> None:
    credit = CreatorCreditRecord(
        provider_key="mangaupdates",
        external_id=None,
        name="DISCIPLES (Redice Studio)",
        role="artist",
        source_url=None,
    )
    initial = await upsert_and_commit(
        ingestion_db,
        make_record(
            creator_credits=(credit,),
        ),
    )
    manga_id = initial.manga.manga_id
    assert manga_id is not None

    manga = await load_manga(
        ingestion_db,
        manga_id=manga_id,
    )
    initial_link = manga.creator_links[0]
    creator_id = initial_link.creator_id

    assert creator_id is not None
    assert initial_link.creator.creator_name == (
        "DISCIPLES (Redice Studio)"
    )
    assert initial_link.role == "artist"
    assert await ingestion_db.scalar_one_or_none(
        select(CreatorExternalSource).where(
            CreatorExternalSource.creator_id
            == creator_id
        )
    ) is None
    refreshed = await upsert_and_commit(
        ingestion_db,
        make_record(
            payload_hash="b" * 64,
            creator_credits=(credit,),
        ),
    )

    assert refreshed.manga.manga_id == manga_id
    assert refreshed.created is False
    assert refreshed.changed is True

    manga = await load_manga(
        ingestion_db,
        manga_id=manga_id,
    )

    assert [
        (
            link.creator_id,
            link.creator.creator_name,
            link.role,
        )
        for link in manga.creator_links
    ] == [
        (
            creator_id,
            "DISCIPLES (Redice Studio)",
            "artist",
        )
    ]
    assert await ingestion_db.scalar_one_or_none(
        select(CreatorExternalSource).where(
            CreatorExternalSource.creator_id
            == creator_id
        )
    ) is None
    matching_creators = await ingestion_db.scalars_all(
        select(Creator).where(
            Creator.creator_name
            == "DISCIPLES (Redice Studio)"
        )
    )

    assert [
        creator.creator_id
        for creator in matching_creators
    ] == [creator_id]


@pytest.mark.asyncio
async def test_identity_uses_provider_and_external_id_not_title(
    ingestion_db: ClientWriteDatabase,
) -> None:
    first = await upsert_and_commit(
        ingestion_db,
        make_record(
            external_id="100",
            title="Shared Title",
            payload_hash="1" * 64,
            creator_credits=(),
        ),
    )
    second = await upsert_and_commit(
        ingestion_db,
        make_record(
            external_id="200",
            title="Shared Title",
            payload_hash="2" * 64,
            creator_credits=(),
        ),
    )
    third = await upsert_and_commit(
        ingestion_db,
        make_record(
            provider_key="another-provider",
            external_id="100",
            title="Shared Title",
            payload_hash="3" * 64,
            creator_credits=(),
        ),
        display_name="Another Provider",
        attribution_url="https://example.com/",
    )

    manga_ids = {
        first.manga.manga_id,
        second.manga.manga_id,
        third.manga.manga_id,
    }

    assert None not in manga_ids
    assert len(manga_ids) == 3

    sources = await ingestion_db.scalars_all(
        select(MangaExternalSource)
    )
    providers = await ingestion_db.scalars_all(
        select(DataProvider)
    )

    provider_keys = {
        provider.provider_id: provider.provider_key
        for provider in providers
    }
    identities = {
        (
            provider_keys[source.provider_id],
            source.external_id,
        )
        for source in sources
    }

    assert identities == {
        ("mangaupdates", "100"),
        ("mangaupdates", "200"),
        ("another-provider", "100"),
    }


@pytest.mark.asyncio
async def test_refresh_preserves_user_owned_rows(
    ingestion_db: ClientWriteDatabase,
    user_write_engine: Engine,
) -> None:
    initial = await upsert_and_commit(
        ingestion_db,
        make_record(),
    )
    manga_id = initial.manga.manga_id
    assert manga_id is not None

    user_id = uuid4()

    with Session(user_write_engine) as session:
        user = User(
            id=user_id,
            email="preservation@example.com",
            username="preservation-user",
            displayname="Preservation User",
            hashed_password="not-used",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        collection = Collection(
            user_id=user_id,
            collection_name="Preserved Collection",
        )

        session.add(user)
        session.add(collection)
        session.flush()

        collection_id = collection.collection_id

        session.add(
            Rating(
                user_id=user_id,
                manga_id=manga_id,
                personal_rating=Decimal("9.0"),
            )
        )
        session.add(
            MangaCollection(
                collection_id=collection_id,
                manga_id=manga_id,
            )
        )
        session.commit()

    updated = make_record(
        payload_hash="b" * 64,
        title="Updated Without Losing User Data",
        genres=("Drama",),
        tags=(),
        demographics=(),
        creator_credits=(),
    )
    outcome = await upsert_and_commit(
        ingestion_db,
        updated,
    )

    assert outcome.manga.manga_id == manga_id

    with Session(user_write_engine) as session:
        rating = session.scalar(
            select(Rating).where(
                Rating.user_id == user_id,
                Rating.manga_id == manga_id,
            )
        )
        membership = session.scalar(
            select(MangaCollection).where(
                MangaCollection.collection_id
                == collection_id,
                MangaCollection.manga_id == manga_id,
            )
        )
        collection = session.get(
            Collection,
            collection_id,
        )

        assert rating is not None
        assert rating.personal_rating == Decimal("9.0")
        assert membership is not None
        assert collection is not None


@pytest.mark.asyncio
async def test_unchanged_source_rejects_missing_manga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = make_record()
    provider = DataProvider(
        provider_id=1,
        provider_key="mangaupdates",
        display_name="MangaUpdates",
        attribution_url=(
            "https://www.mangaupdates.com/"
        ),
    )
    source = MangaExternalSource(
        manga_id=999,
        provider_id=1,
        external_id=record.external_id,
        source_url=record.source_url,
        payload_hash=record.payload_hash,
    )

    user_db = MagicMock(spec=ClientWriteDatabase)
    user_db.get = AsyncMock(return_value=None)

    monkeypatch.setattr(
        repository,
        "_get_or_create_provider",
        AsyncMock(return_value=provider),
    )
    monkeypatch.setattr(
        repository,
        "_find_manga_source",
        AsyncMock(return_value=source),
    )

    with pytest.raises(
        RuntimeError,
        match="references a missing manga",
    ):
        await repository.upsert_catalog_manga(
            user_db,
            record=record,
            provider_display_name="MangaUpdates",
            provider_attribution_url=(
                "https://www.mangaupdates.com/"
            ),
        )
