from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.cache import invalidation


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_deletes_all_collection_keys(
    monkeypatch,
):
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            [
                (1,),
                (5,),
                (12,),
            ]
        )
    )

    cache = MagicMock()
    cache.delete_multiple = AsyncMock()

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    await invalidation.invalidate_user_recommendations(
        db,
        user_id,
    )

    db.execute.assert_awaited_once()

    cache.delete_multiple.assert_awaited_once_with(
        f"recommendations:{user_id}:1",
        f"recommendations:{user_id}:5",
        f"recommendations:{user_id}:12",
    )


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_builds_owned_collection_query(
    monkeypatch,
):
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult([])
    )

    cache = MagicMock()
    cache.delete_multiple = AsyncMock()

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    await invalidation.invalidate_user_recommendations(
        db,
        user_id,
    )

    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert "collection.collection_id" in sql
    assert "collection.user_id" in sql
    assert user_id in compiled.params.values()


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_does_not_delete_when_user_has_no_collections(
    monkeypatch,
):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult([])
    )

    cache = MagicMock()
    cache.delete_multiple = AsyncMock()

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    await invalidation.invalidate_user_recommendations(
        db,
        uuid.uuid4(),
    )

    db.execute.assert_awaited_once()
    cache.delete_multiple.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_propagates_database_error(
    monkeypatch,
):
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )

    cache = MagicMock()
    cache.delete_multiple = AsyncMock()

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        await invalidation.invalidate_user_recommendations(
            db,
            uuid.uuid4(),
        )

    cache.delete_multiple.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_propagates_cache_error(
    monkeypatch,
):
    user_id = uuid.uuid4()

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            [
                (2,),
                (3,),
            ]
        )
    )

    cache = MagicMock()
    cache.delete_multiple = AsyncMock(
        side_effect=RuntimeError("cache failure")
    )

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    with pytest.raises(
        RuntimeError,
        match="cache failure",
    ):
        await invalidation.invalidate_user_recommendations(
            db,
            user_id,
        )

    cache.delete_multiple.assert_awaited_once_with(
        f"recommendations:{user_id}:2",
        f"recommendations:{user_id}:3",
    )


@pytest.mark.asyncio
async def test_invalidate_collection_recommendations_deletes_target_key(
    monkeypatch,
):
    user_id = uuid.uuid4()

    cache = MagicMock()
    cache.delete = AsyncMock()

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    await invalidation.invalidate_collection_recommendations(
        user_id,
        42,
    )

    cache.delete.assert_awaited_once_with(
        f"recommendations:{user_id}:42"
    )


@pytest.mark.asyncio
async def test_invalidate_collection_recommendations_propagates_cache_error(
    monkeypatch,
):
    cache = MagicMock()
    cache.delete = AsyncMock(
        side_effect=RuntimeError("cache failure")
    )

    monkeypatch.setattr(
        invalidation,
        "redis_cache",
        cache,
    )

    with pytest.raises(
        RuntimeError,
        match="cache failure",
    ):
        await invalidation.invalidate_collection_recommendations(
            uuid.uuid4(),
            10,
        )