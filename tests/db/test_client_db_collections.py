import pytest
from sqlalchemy import select

from backend.db.client_db import ClientWriteDatabase
from backend.db.models.collection import Collection
from backend.db.models.manga_collection import MangaCollection
from tests.db.factories import make_manga, make_user  # adjust to your factories

@pytest.mark.asyncio
async def test_add_manga_to_collection_inserts_link(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    c = Collection(user_id=user.id, collection_name="C1", description="d")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    db = ClientWriteDatabase(db_session)

    await db.add_manga_to_collection(user.id, c.collection_id, manga.manga_id)

    res = await db_session.execute(
        select(MangaCollection).where(
            MangaCollection.collection_id == c.collection_id,
            MangaCollection.manga_id == manga.manga_id,
        )
    )
    assert res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_add_manga_duplicate_behavior(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    c = Collection(user_id=user.id, collection_name="C2", description="d")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    db = ClientWriteDatabase(db_session)

    await db.add_manga_to_collection(user.id, c.collection_id, manga.manga_id)

    with pytest.raises(ValueError) as exc:
        await db.add_manga_to_collection(user.id, c.collection_id, manga.manga_id)

    assert "already" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_add_manga_collection_missing_raises(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)
    db = ClientWriteDatabase(db_session)

    with pytest.raises(ValueError):
        await db.add_manga_to_collection(user.id, 999999, manga.manga_id)


@pytest.mark.asyncio
async def test_remove_manga_from_collection_missing_link_raises(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    c = Collection(user_id=user.id, collection_name="C3", description="d")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    db = ClientWriteDatabase(db_session)

    with pytest.raises(ValueError):
        await db.remove_manga_from_collection(user.id, c.collection_id, manga.manga_id)


@pytest.mark.asyncio
async def test_remove_manga_from_collection_deletes_link(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    c = Collection(user_id=user.id, collection_name="C4", description="d")
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)

    # insert link directly
    link = MangaCollection(collection_id=c.collection_id, manga_id=manga.manga_id)
    db_session.add(link)
    await db_session.commit()

    db = ClientWriteDatabase(db_session)

    await db.remove_manga_from_collection(user.id, c.collection_id, manga.manga_id)

    res = await db_session.execute(
        select(MangaCollection).where(
            MangaCollection.collection_id == c.collection_id,
            MangaCollection.manga_id == manga.manga_id,
        )
    )
    assert res.scalar_one_or_none() is None
