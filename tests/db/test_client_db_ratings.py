# tests/db/test_client_db_ratings.py
import pytest

from backend.db.client_db import ClientWriteDatabase
from tests.db.factories import make_user, make_manga, make_rating


def test_normalize_score_clamps_and_snaps():
    assert ClientWriteDatabase._normalize_score(-1.0) == 0.0
    assert ClientWriteDatabase._normalize_score(0.0) == 0.0
    assert ClientWriteDatabase._normalize_score(10.6) == 10.0
    assert ClientWriteDatabase._normalize_score(9.74) == 9.5
    assert ClientWriteDatabase._normalize_score(9.76) == 10.0
    assert ClientWriteDatabase._normalize_score(7.26) == 7.5

    with pytest.raises(ValueError):
        ClientWriteDatabase._normalize_score(None)


@pytest.mark.asyncio
async def test_rate_manga_creates_and_updates(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    client_db = ClientWriteDatabase(db_session)

    # Create rating
    r1 = await client_db.rate_manga(user.id, manga.manga_id, 7.26)
    assert r1.user_id == user.id
    assert r1.manga_id == manga.manga_id
    assert r1.personal_rating == 7.5  # snapped

    # Update rating
    r2 = await client_db.rate_manga(user.id, manga.manga_id, 8.9)
    assert r2.user_id == user.id
    assert r2.manga_id == manga.manga_id
    assert r2.personal_rating == 9.0

    # Ensure only one rating exists
    all_ratings = await client_db.get_all_user_ratings(user.id)
    assert len(all_ratings) == 1
    assert all_ratings[0].personal_rating == 9.0


@pytest.mark.asyncio
async def test_rate_manga_raises_on_none_score(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    client_db = ClientWriteDatabase(db_session)

    with pytest.raises(ValueError):
        await client_db.rate_manga(user.id, manga.manga_id, None)


@pytest.mark.asyncio
async def test_get_user_rating_for_manga_none_when_missing(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)

    client_db = ClientWriteDatabase(db_session)

    r = await client_db.get_user_rating_for_manga(user.id, manga.manga_id)
    assert r is None


@pytest.mark.asyncio
async def test_get_user_rating_for_manga_returns_when_present(db_session):
    user = await make_user(db_session)
    manga = await make_manga(db_session)
    await make_rating(db_session, user=user, manga=manga, personal_rating=8.5)

    client_db = ClientWriteDatabase(db_session)

    r = await client_db.get_user_rating_for_manga(user.id, manga.manga_id)
    assert r is not None
    assert r.user_id == user.id
    assert r.manga_id == manga.manga_id
    assert r.personal_rating == 8.5


@pytest.mark.asyncio
async def test_get_all_user_ratings_empty_when_none(db_session):
    user = await make_user(db_session)

    client_db = ClientWriteDatabase(db_session)

    ratings = await client_db.get_all_user_ratings(user.id)
    assert ratings == []


@pytest.mark.asyncio
async def test_get_all_user_ratings_returns_list(db_session):
    user = await make_user(db_session)
    m1 = await make_manga(db_session)
    m2 = await make_manga(db_session)

    await make_rating(db_session, user=user, manga=m1, personal_rating=6.0)
    await make_rating(db_session, user=user, manga=m2, personal_rating=9.5)

    client_db = ClientWriteDatabase(db_session)

    ratings = await client_db.get_all_user_ratings(user.id)
    assert len(ratings) == 2
    assert {r.manga_id for r in ratings} == {m1.manga_id, m2.manga_id}
