from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.repositories import rating_repo


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value


class FakeScalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class FakePageResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return FakeScalars(self._values)


@pytest.mark.asyncio
async def test_fetch_user_rating_returns_rating():
    user_id = uuid.uuid4()
    rating = MagicMock()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(rating)
    )

    result = await rating_repo.fetch_user_rating(
        db,
        user_id=user_id,
        manga_id=25,
    )

    assert result is rating
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_user_rating_returns_none_when_missing():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(None)
    )

    result = await rating_repo.fetch_user_rating(
        db,
        user_id=uuid.uuid4(),
        manga_id=25,
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_user_rating_builds_expected_query():
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(None)
    )

    await rating_repo.fetch_user_rating(
        db,
        user_id=user_id,
        manga_id=77,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "rating.user_id" in sql
    assert "rating.manga_id" in sql
    assert user_id in compiled.params.values()
    assert 77 in compiled.params.values()


@pytest.mark.asyncio
async def test_fetch_user_rating_propagates_database_error():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        await rating_repo.fetch_user_rating(
            db,
            user_id=uuid.uuid4(),
            manga_id=10,
        )


@pytest.mark.asyncio
async def test_list_user_ratings_returns_all_rows_in_stable_order():
    user_id = uuid.uuid4()
    rating_one = MagicMock(manga_id=10)
    rating_two = MagicMock(manga_id=20)
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakePageResult(
            [rating_one, rating_two]
        )
    )

    result = await rating_repo.list_user_ratings(
        db,
        user_id=user_id,
    )

    assert result == [rating_one, rating_two]
    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "rating.user_id" in sql
    assert "ORDER BY rating.manga_id ASC" in sql
    assert "LIMIT" not in sql
    assert "OFFSET" not in sql
    assert user_id in compiled.params.values()


@pytest.mark.asyncio
async def test_upsert_user_rating_delegates_to_database_wrapper():
    user_id = uuid.uuid4()
    saved_rating = MagicMock()

    db = MagicMock()
    db.rate_manga = AsyncMock(
        return_value=saved_rating
    )

    result = await rating_repo.upsert_user_rating(
        db,
        user_id=user_id,
        manga_id=100,
        score=4.5,
    )

    assert result is saved_rating

    db.rate_manga.assert_awaited_once_with(
        user_id=user_id,
        manga_id=100,
        score=4.5,
    )


@pytest.mark.asyncio
async def test_upsert_user_rating_propagates_database_error():
    db = MagicMock()
    db.rate_manga = AsyncMock(
        side_effect=RuntimeError("upsert failed")
    )

    with pytest.raises(
        RuntimeError,
        match="upsert failed",
    ):
        await rating_repo.upsert_user_rating(
            db,
            user_id=uuid.uuid4(),
            manga_id=100,
            score=4.5,
        )
