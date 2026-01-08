import pytest

from backend.cache.invalidation import (
    invalidate_user_recommendations,
    invalidate_collection_recommendations,
)


class FakeResult:
    def __init__(self, rows):
        # rows should look like [(1,), (2,), ...]
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = False

    async def execute(self, _stmt):
        self.executed = True
        return FakeResult(self._rows)


class FakeDB:
    def __init__(self, rows):
        self.session = FakeSession(rows)


class FakeRedis:
    def __init__(self):
        self.deleted = []
        self.deleted_multiple = []

    async def delete(self, key: str):
        self.deleted.append(key)

    async def delete_multiple(self, *keys: str):
        self.deleted_multiple.append(list(keys))


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_deletes_all_keys(monkeypatch):
    fake_redis = FakeRedis()

    import backend.cache.invalidation as invalidation_module
    monkeypatch.setattr(invalidation_module, "redis_cache", fake_redis)

    db = FakeDB(rows=[(1,), (2,), (3,)])
    user_id = "user-uuid"

    await invalidate_user_recommendations(db, user_id)

    assert db.session.executed is True
    assert fake_redis.deleted == []  # should not delete
    assert fake_redis.deleted_multiple == [
        [
            "recommendations:user-uuid:1",
            "recommendations:user-uuid:2",
            "recommendations:user-uuid:3",
        ]
    ]


@pytest.mark.asyncio
async def test_invalidate_user_recommendations_no_collections_no_delete(monkeypatch):
    fake_redis = FakeRedis()

    import backend.cache.invalidation as invalidation_module
    monkeypatch.setattr(invalidation_module, "redis_cache", fake_redis)

    db = FakeDB(rows=[])
    user_id = "user-uuid"

    await invalidate_user_recommendations(db, user_id)

    assert db.session.executed is True
    assert fake_redis.deleted == []
    assert fake_redis.deleted_multiple == []  # no keys = no delete_multiple call


@pytest.mark.asyncio
async def test_invalidate_collection_recommendations_deletes_single_key(monkeypatch):
    fake_redis = FakeRedis()

    import backend.cache.invalidation as invalidation_module
    monkeypatch.setattr(invalidation_module, "redis_cache", fake_redis)

    await invalidate_collection_recommendations("user-uuid", 99)

    assert fake_redis.deleted == ["recommendations:user-uuid:99"]
    assert fake_redis.deleted_multiple == []
