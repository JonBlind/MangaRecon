from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.db import client_db
from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)
from backend.utils.domain_exceptions import NotFoundError


@pytest.fixture
def session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_get_user_rating_for_manga_returns_rating(
    session,
):
    user_id = uuid.uuid4()
    rating = MagicMock()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = rating
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_user_rating_for_manga(
        user_id,
        10,
    )

    assert result is rating

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "rating.user_id" in sql
    assert "rating.manga_id" in sql
    assert user_id in compiled.params.values()
    assert 10 in compiled.params.values()


@pytest.mark.asyncio
async def test_get_user_rating_for_manga_returns_none_when_missing(
    session,
):
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_user_rating_for_manga(
        uuid.uuid4(),
        10,
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_user_rating_for_manga_returns_none_on_sqlalchemy_error(
    monkeypatch,
    session,
):
    session.execute.side_effect = SQLAlchemyError(
        "query failed"
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientReadDatabase(session)

    result = await db.get_user_rating_for_manga(
        uuid.uuid4(),
        10,
    )

    assert result is None
    log_error.assert_called_once()
    assert log_error.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_get_all_user_ratings_returns_rows(
    session,
):
    ratings = [MagicMock(), MagicMock()]

    scalar_result = MagicMock()
    scalar_result.all.return_value = ratings

    query_result = MagicMock()
    query_result.scalars.return_value = scalar_result

    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_all_user_ratings(
        uuid.uuid4()
    )

    assert result == ratings


@pytest.mark.asyncio
async def test_get_all_user_ratings_returns_empty_list_on_error(
    monkeypatch,
    session,
):
    session.execute.side_effect = SQLAlchemyError(
        "query failed"
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientReadDatabase(session)

    result = await db.get_all_user_ratings(
        uuid.uuid4()
    )

    assert result == []
    log_error.assert_called_once()


@pytest.mark.asyncio
async def test_rate_manga_updates_existing_rating(
    monkeypatch,
    session,
):
    user_id = uuid.uuid4()
    manga = MagicMock()
    existing_rating = MagicMock()
    existing_rating.personal_rating = 1.0

    session.get.side_effect = [
        manga,
        existing_rating,
    ]

    log_info = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "info",
        log_info,
    )

    db = ClientWriteDatabase(session)

    result = await db.rate_manga(
        user_id,
        25,
        8.24,
    )

    assert result is existing_rating
    assert existing_rating.personal_rating == 8.0

    assert session.get.await_args_list[0].args == (
        client_db.Manga,
        25,
    )
    assert session.get.await_args_list[1].args == (
        client_db.Rating,
        (user_id, 25),
    )

    session.add.assert_not_called()
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(
        existing_rating
    )
    session.rollback.assert_not_awaited()

    assert "Updated rating" in log_info.call_args.args[0]


@pytest.mark.asyncio
async def test_rate_manga_creates_new_rating(
    monkeypatch,
    session,
):
    user_id = uuid.uuid4()
    manga = MagicMock()
    new_rating = MagicMock()

    session.get.side_effect = [
        manga,
        None,
    ]

    rating_constructor = MagicMock(
        return_value=new_rating
    )
    monkeypatch.setattr(
        client_db,
        "Rating",
        rating_constructor,
    )

    db = ClientWriteDatabase(session)

    result = await db.rate_manga(
        user_id,
        25,
        9.26,
    )

    assert result is new_rating

    rating_constructor.assert_called_once_with(
        user_id=user_id,
        manga_id=25,
        personal_rating=9.5,
    )

    session.add.assert_called_once_with(new_rating)
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(
        new_rating
    )


@pytest.mark.asyncio
async def test_rate_manga_raises_when_manga_does_not_exist(
    session,
):
    session.get.return_value = None

    db = ClientWriteDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.rate_manga(
            uuid.uuid4(),
            999,
            5.0,
        )

    error = exc_info.value

    assert error.code == "MANGA_NOT_FOUND"
    assert error.message == "Manga not found."

    session.commit.assert_not_awaited()
    session.refresh.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_manga_rolls_back_on_commit_error(
    session,
):
    manga = MagicMock()
    rating = MagicMock()

    session.get.side_effect = [
        manga,
        rating,
    ]
    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="commit failed",
    ):
        await db.rate_manga(
            uuid.uuid4(),
            10,
            7.0,
        )

    session.rollback.assert_awaited_once_with()
    session.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_rate_manga_rolls_back_on_refresh_error(
    session,
):
    manga = MagicMock()
    rating = MagicMock()

    session.get.side_effect = [
        manga,
        rating,
    ]
    session.refresh.side_effect = SQLAlchemyError(
        "refresh failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="refresh failed",
    ):
        await db.rate_manga(
            uuid.uuid4(),
            10,
            7.0,
        )

    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_rating_deletes_and_commits(
    session,
):
    user_id = uuid.uuid4()
    rating = MagicMock()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = rating
    session.execute.return_value = query_result

    db = ClientWriteDatabase(session)

    result = await db.delete_rating(
        user_id,
        25,
    )

    assert result is None

    session.delete.assert_awaited_once_with(rating)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert user_id in compiled.params.values()
    assert 25 in compiled.params.values()


@pytest.mark.asyncio
async def test_delete_rating_raises_when_rating_missing(
    session,
):
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result

    db = ClientWriteDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.delete_rating(
            uuid.uuid4(),
            25,
        )

    assert exc_info.value.code == "RATING_NOT_FOUND"

    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_rating_rolls_back_on_commit_error(
    session,
):
    rating = MagicMock()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = rating
    session.execute.return_value = query_result

    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="commit failed",
    ):
        await db.delete_rating(
            uuid.uuid4(),
            25,
        )

    session.delete.assert_awaited_once_with(rating)
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_rating_propagates_execute_error_without_rollback(
    session,
):
    session.execute.side_effect = SQLAlchemyError(
        "query failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="query failed",
    ):
        await db.delete_rating(
            uuid.uuid4(),
            25,
        )

    session.rollback.assert_not_awaited()