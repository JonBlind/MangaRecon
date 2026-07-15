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
async def test_count_user_ratings_returns_count():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(8)
    )

    result = await rating_repo.count_user_ratings(
        db,
        user_id=uuid.uuid4(),
    )

    assert result == 8
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_user_ratings_builds_count_query():
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(0)
    )

    await rating_repo.count_user_ratings(
        db,
        user_id=user_id,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "count(" in sql.lower()
    assert "rating.user_id" in sql
    assert "ORDER BY" not in sql.upper()
    assert user_id in compiled.params.values()


@pytest.mark.asyncio
async def test_count_user_ratings_propagates_database_error():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("count failed")
    )

    with pytest.raises(
        RuntimeError,
        match="count failed",
    ):
        await rating_repo.count_user_ratings(
            db,
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_page_user_ratings_returns_rating_list():
    rating_one = MagicMock()
    rating_two = MagicMock()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakePageResult(
            [
                rating_one,
                rating_two,
            ]
        )
    )

    result = await rating_repo.page_user_ratings(
        db,
        user_id=uuid.uuid4(),
        offset=10,
        limit=5,
    )

    assert result == [
        rating_one,
        rating_two,
    ]


@pytest.mark.asyncio
async def test_page_user_ratings_returns_empty_list():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakePageResult([])
    )

    result = await rating_repo.page_user_ratings(
        db,
        user_id=uuid.uuid4(),
        offset=0,
        limit=10,
    )

    assert result == []


@pytest.mark.asyncio
async def test_page_user_ratings_builds_expected_query():
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakePageResult([])
    )

    await rating_repo.page_user_ratings(
        db,
        user_id=user_id,
        offset=15,
        limit=5,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "rating.user_id" in sql
    assert "ORDER BY rating.manga_id ASC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql

    params = list(compiled.params.values())

    assert user_id in params
    assert 15 in params
    assert 5 in params


@pytest.mark.asyncio
async def test_page_user_ratings_propagates_database_error():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("page failed")
    )

    with pytest.raises(
        RuntimeError,
        match="page failed",
    ):
        await rating_repo.page_user_ratings(
            db,
            user_id=uuid.uuid4(),
            offset=0,
            limit=10,
        )


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