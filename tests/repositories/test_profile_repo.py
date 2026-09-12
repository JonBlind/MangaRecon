from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.repositories import profile_repo


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_fetch_user_by_id_returns_user():
    user_id = uuid.uuid4()
    user = MagicMock()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(user)
    )

    result = await profile_repo.fetch_user_by_id(
        db,
        user_id=user_id,
    )

    assert result is user
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_user_by_id_returns_none_when_missing():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(None)
    )

    result = await profile_repo.fetch_user_by_id(
        db,
        user_id=uuid.uuid4(),
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_user_by_id_builds_expected_query():
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeScalarResult(None)
    )

    await profile_repo.fetch_user_by_id(
        db,
        user_id=user_id,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "FROM" in sql
    assert "user" in sql.lower()
    assert "WHERE" in sql
    assert user_id in compiled.params.values()


@pytest.mark.asyncio
async def test_fetch_user_by_id_propagates_database_error():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        await profile_repo.fetch_user_by_id(
            db,
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_fetch_user_for_deletion_locks_only_current_user():
    user_id = uuid.uuid4()
    user = MagicMock()
    db = MagicMock()
    db.execute = AsyncMock(return_value=FakeScalarResult(user))

    result = await profile_repo.fetch_user_for_deletion(db, user_id=user_id)

    assert result is user
    statement = db.execute.await_args.args[0]
    assert "FOR UPDATE" in str(statement)
    assert user_id in statement.compile().params.values()


@pytest.mark.asyncio
async def test_get_owned_collection_ids_uses_user_filter():
    user_id = uuid.uuid4()
    db = MagicMock()
    db.scalars_all = AsyncMock(return_value=[3, 7])

    result = await profile_repo.get_owned_collection_ids(db, user_id=user_id)

    assert result == [3, 7]
    statement = db.scalars_all.await_args.args[0]
    assert "collection.user_id" in str(statement)
    assert user_id in statement.compile().params.values()


@pytest.mark.asyncio
async def test_delete_user_row_uses_database_cascades():
    user_id = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock()

    await profile_repo.delete_user_row(db, user_id=user_id)

    statement = db.execute.await_args.args[0]
    assert str(statement).startswith("DELETE FROM")
    assert user_id in statement.compile().params.values()
    assert "user" in str(statement).lower()
