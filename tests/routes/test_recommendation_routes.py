import pytest

from tests.db.factories import make_manga
from backend.config.limits import MAX_RECOMMENDATION_SEEDS
from backend.routes import recommendation_routes as rec_routes
import backend.cache.invalidation as inv
import backend.routes.collection_routes as col_routes_real
import backend.recommendation.core as core


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.get_calls = []
        self.set_calls = []
        self.delete_calls = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return self.store.get(key)

    async def set(self, key: str, value):
        self.set_calls.append((key, value))
        self.store[key] = value

    async def delete(self, key: str):
        self.delete_calls.append(key)
        self.store.pop(key, None)


async def _create_collection(async_client, name="Test Collection", description="desc"):
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": name, "description": description},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    return body["data"]["collection_id"]


@pytest.mark.asyncio
async def test_recommendations_missing_collection_returns_404(async_client):
    resp = await async_client.get("/recommendations/999999?page=1&size=20")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_recommendations_cache_hit_skips_generator(async_client, monkeypatch):

    collection_id = await _create_collection(async_client)
    fake_redis = FakeRedis()

    cached_items = [
        {"manga_id": 1, "title": "B", "score": 0.0},
        {"manga_id": 2, "title": "A", "score": 9.5},
    ]

    async def fake_get(key):
        return cached_items

    async def fake_set(key, val):
        raise AssertionError("set should not be called on cache hit")

    fake_redis.get = fake_get
    fake_redis.set = fake_set

    async def generator_should_not_run(*args, **kwargs):
        raise AssertionError("generate_recommendations_for_collection should not be called on cache hit")

    monkeypatch.setattr(rec_routes, "redis_cache", fake_redis, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", generator_should_not_run, raising=True)

    resp = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=1&size=20")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["items"][0]["score"] == 9.5


@pytest.mark.asyncio
async def test_recommendations_cache_miss_sets_cache_and_second_call_hits(async_client, monkeypatch):

    collection_id = await _create_collection(async_client)
    fake_redis = FakeRedis()

    calls = {"gen": 0}
    generated = [
        {"manga_id": 1, "title": "Z", "score": 1.0},
        {"manga_id": 2, "title": "A", "score": 10.0},
    ]

    async def fake_generate(*args, **kwargs):
        calls["gen"] += 1
        return {
            "items": list(generated),
            "seed_total": 2,
            "seed_used": 2,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "redis_cache", fake_redis, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_generate, raising=True)

    # 1st call -> miss -> generate -> set
    r1 = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=1&size=20")
    assert r1.status_code == 200, r1.text
    assert calls["gen"] == 1
    assert len(fake_redis.set_calls) == 1

    # 2nd call -> hit -> no generate
    r2 = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=1&size=20")
    assert r2.status_code == 200, r2.text
    assert calls["gen"] == 1  # unchanged


@pytest.mark.asyncio
async def test_recommendations_sort_and_paginate(async_client, monkeypatch):

    # 1) create a collection
    c = await async_client.post("/collections/", json={"collection_name": "RecTest", "description": "d"})
    cid = c.json()["data"]["collection_id"]

    fake_items = [
        {"manga_id": 1, "title": "Bleach", "score": 0.2},
        {"manga_id": 2, "title": "Attack on Titan", "score": 0.9},
        {"manga_id": 3, "title": "Chainsaw Man", "score": 0.9},
        {"manga_id": 4, "title": "Naruto", "score": 0.1},
    ]

    async def _fake_gen(user_id, collection_id, db):
        return {
            "items": list(fake_items),
            "seed_total": 4,
            "seed_used": 4,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", _fake_gen, raising=True)
    # ensure cache doesn't interfere
    monkeypatch.setattr(rec_routes, "redis_cache", FakeRedis(), raising=True)

    # call with ordering by score desc, size=2
    r1 = await async_client.get(f"/recommendations/{cid}?order_by=score&order_dir=desc&page=1&size=2")
    assert r1.status_code == 200, r1.text
    items = r1.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["score"] == 0.9
    assert items[1]["score"] == 0.9

    # page 2 should continue
    r2 = await async_client.get(f"/recommendations/{cid}?order_by=score&order_dir=desc&page=2&size=2")
    assert r2.status_code == 200, r2.text
    items2 = r2.json()["data"]["items"]
    assert len(items2) == 2
    assert {i["manga_id"] for i in items2} == {1, 4}


@pytest.mark.asyncio
async def test_recommendations_are_cached(async_client, db_session, monkeypatch):

    manga = await make_manga(db_session)

    # create collection
    c = await async_client.post(
        "/collections/",
        json={"collection_name": "RecCache", "description": "d"},
    )
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    # add manga so generator has input
    add = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert add.status_code == 200, add.text

    calls = {"n": 0}

    async def fake_generate(user_id, collection_id, db):
        calls["n"] += 1
        return {
            "items": [
                {"manga_id": 123, "title": "X", "score": 0.9},
                {"manga_id": 456, "title": "Y", "score": 0.5},
            ],
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
        }

    fake_cache = FakeRedis()
    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_generate, raising=True)
    monkeypatch.setattr(rec_routes, "redis_cache", fake_cache, raising=True)

    # first call -> miss -> generator runs
    r1 = await async_client.get(f"/recommendations/{cid}?page=1&size=20&order_by=score&order_dir=desc")
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "success"
    assert calls["n"] == 1
    assert len(fake_cache.set_calls) == 1

    # second call -> hit -> generator should NOT run again
    r2 = await async_client.get(f"/recommendations/{cid}?page=1&size=20&order_by=score&order_dir=desc")
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "success"
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_add_manga_invalidates_recommendations(async_client, db_session, monkeypatch):

    manga1 = await make_manga(db_session)
    manga2 = await make_manga(db_session)

    # create collection
    c = await async_client.post("/collections/", json={"collection_name": "InvAdd", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    # add initial manga so recs can generate
    add1 = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga1.manga_id})
    assert add1.status_code == 200, add1.text

    fake_cache = FakeRedis()
    monkeypatch.setattr(rec_routes, "redis_cache", fake_cache, raising=True)

    calls = {"n": 0}

    async def fake_generate(user_id, collection_id, db):
        calls["n"] += 1
        return {
            "items": [{"manga_id": 1, "title": f"gen{calls['n']}", "score": 0.9}],
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_generate, raising=True)

    async def fake_invalidate(user_id, collection_id):
        await fake_cache.delete(f"recommendations:{user_id}:{collection_id}")

    monkeypatch.setattr(col_routes_real, "invalidate_collection_recommendations", fake_invalidate, raising=True)
    monkeypatch.setattr(inv, "invalidate_collection_recommendations", fake_invalidate, raising=True)

    # first rec call -> caches
    r1 = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r1.status_code == 200, r1.text
    assert calls["n"] == 1
    assert len(fake_cache.set_calls) == 1

    # second rec call -> should hit cache (no new generator call)
    r2 = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r2.status_code == 200, r2.text
    assert calls["n"] == 1

    # add another manga -> should invalidate
    add2 = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga2.manga_id})
    assert add2.status_code == 200, add2.text

    assert len(fake_cache.delete_calls) == 1, fake_cache.delete_calls

    # third rec call -> should MISS cache and regenerate
    r3 = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r3.status_code == 200, r3.text
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_other_user_cannot_get_recommendations_for_collection_returns_404(
    async_client,
    async_client_other_user,
    db_session,
):
    manga = await make_manga(db_session)

    # user A creates collection and adds manga
    c = await async_client.post("/collections/", json={"collection_name": "RecPrivate", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    add = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert add.status_code == 200, add.text

    # user B tries to get recs for A's collection
    r = await async_client_other_user.get(f"/recommendations/{cid}?page=1&size=20")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_query_list_recommendations_public_access(_raw_async_client, monkeypatch):

    fake_items = [
        {"manga_id": 1, "title": "B", "score": 0.2},
        {"manga_id": 2, "title": "A", "score": 0.9},
    ]

    async def fake_gen(manga_ids, db):
        return {
            "items": list(fake_items),
            "seed_total": len(manga_ids),
            "seed_used": len(manga_ids),
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_list", fake_gen, raising=True)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20&order_by=score&order_dir=desc",
        json={"manga_ids": [111, 222]},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    assert "items" in body["data"]
    assert body["data"]["items"][0]["score"] == 0.9


@pytest.mark.asyncio
async def test_query_list_recommendations_dedupes_ids(_raw_async_client, monkeypatch):

    captured = {}

    async def fake_gen(manga_ids, db):
        captured["manga_ids"] = manga_ids
        return {
            "items": [{"manga_id": 1, "title": "X", "score": 1.0}],
            "seed_total": len(manga_ids),
            "seed_used": len(manga_ids),
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_list", fake_gen, raising=True)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20",
        json={"manga_ids": [5, 5, 6, 6, 7]},
    )
    assert resp.status_code == 200, resp.text
    assert captured["manga_ids"] == [5, 6, 7]


@pytest.mark.asyncio
async def test_query_list_recommendations_sort_and_paginate(_raw_async_client, monkeypatch):

    fake_items = [
        {"manga_id": 1, "title": "Bleach", "score": 0.2},
        {"manga_id": 2, "title": "Attack on Titan", "score": 0.9},
        {"manga_id": 3, "title": "Chainsaw Man", "score": 0.9},
        {"manga_id": 4, "title": "Naruto", "score": 0.1},
    ]

    async def fake_gen(manga_ids, db):
        return {
            "items": list(fake_items),
            "seed_total": len(manga_ids),
            "seed_used": len(manga_ids),
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_list", fake_gen, raising=True)

    r1 = await _raw_async_client.post(
        "/recommendations/query-list?order_by=score&order_dir=desc&page=1&size=2",
        json={"manga_ids": [1, 2]},
    )
    assert r1.status_code == 200, r1.text
    items = r1.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["score"] == 0.9
    assert items[1]["score"] == 0.9

    r2 = await _raw_async_client.post(
        "/recommendations/query-list?order_by=score&order_dir=desc&page=2&size=2",
        json={"manga_ids": [1, 2]},
    )
    assert r2.status_code == 200, r2.text
    items2 = r2.json()["data"]["items"]
    assert {i["manga_id"] for i in items2} == {1, 4}

@pytest.mark.asyncio
async def test_query_list_recommendations_end_to_end(_raw_async_client, db_session, monkeypatch):
    monkeypatch.setattr(rec_routes, "redis_cache", FakeRedis(), raising=True)

    m1 = await make_manga(db_session)
    m2 = await make_manga(db_session)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20&order_by=score&order_dir=desc",
        json={"manga_ids": [m1.manga_id, m2.manga_id]},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]

    assert isinstance(data["items"], list)
    assert "seed_total" in data
    assert "seed_used" in data
    assert "seed_truncated" in data


@pytest.mark.asyncio
async def test_query_list_recommendations_returns_truncation_metadata(_raw_async_client, monkeypatch):
    async def fake_profile(manga_ids, db):
        # This asserts truncation happened inside generator
        assert len(manga_ids) == MAX_RECOMMENDATION_SEEDS
        return {"genres": {}, "tags": {}, "demographics": {}}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        return [{"manga_id": 999, "title": "X"}]

    async def fake_scored(candidates, metadata_profile, db):
        return [{"manga_id": 999, "title": "X", "score": 1.0}]

    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    payload_ids = list(range(MAX_RECOMMENDATION_SEEDS + 20))
    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20",
        json={"manga_ids": payload_ids},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["seed_truncated"] is True
    assert data["seed_used"] == MAX_RECOMMENDATION_SEEDS
    assert data["seed_total"] == MAX_RECOMMENDATION_SEEDS + 20

@pytest.mark.asyncio
async def test_query_list_response_contract_includes_seed_metadata_and_items(_raw_async_client, monkeypatch):

    async def fake_gen(manga_ids, db):
        return {
            "items": [{"manga_id": 1, "title": "X", "score": 1.0}],
            "seed_total": 2,
            "seed_used": 2,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_list", fake_gen, raising=True)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20",
        json={"manga_ids": [11, 22]},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]

    assert "items" in data
    assert "seed_total" in data
    assert "seed_used" in data
    assert "seed_truncated" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_query_list_dedupes_preserving_order(_raw_async_client, monkeypatch):

    captured = {}

    async def fake_gen(manga_ids, db):
        captured["manga_ids"] = manga_ids
        return {
            "items": [],
            "seed_total": len(manga_ids),
            "seed_used": len(manga_ids),
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_list", fake_gen, raising=True)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20",
        json={"manga_ids": [5, 5, 7, 6, 7, 5]},
    )
    assert resp.status_code == 200, resp.text
    assert captured["manga_ids"] == [5, 7, 6]

async def test_collection_recommendations_cache_stores_items_only(async_client, monkeypatch):

    # create collection
    c = await async_client.post("/collections/", json={"collection_name": "CacheShape", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    class FakeRedis:
        def __init__(self):
            self.store = {}
            self.set_calls = []

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value):
            self.set_calls.append((key, value))
            self.store[key] = value

    fake_cache = FakeRedis()

    async def fake_gen(user_id, collection_id, db):
        return {
            "items": [{"manga_id": 1, "title": "X", "score": 0.5}],
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "redis_cache", fake_cache, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_gen, raising=True)

    r = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r.status_code == 200, r.text

    # verify what we cached
    assert len(fake_cache.set_calls) == 1
    _key, cached_val = fake_cache.set_calls[0]
    assert isinstance(cached_val, list)
    assert cached_val == [{"manga_id": 1, "title": "X", "score": 0.5}]

@pytest.mark.asyncio
async def test_remove_manga_invalidates_recommendations(async_client, db_session, monkeypatch):
    manga1 = await make_manga(db_session)

    # create collection
    c = await async_client.post("/collections/", json={"collection_name": "InvRemove", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    # add manga so recs can generate
    add1 = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga1.manga_id})
    assert add1.status_code == 200, add1.text

    class FakeRedis:
        def __init__(self):
            self.store = {}
            self.delete_calls = []

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value):
            self.store[key] = value

        async def delete(self, key):
            self.delete_calls.append(key)
            self.store.pop(key, None)

    fake_cache = FakeRedis()
    monkeypatch.setattr(rec_routes, "redis_cache", fake_cache, raising=True)

    # prime cache via recommendations
    async def fake_gen(user_id, collection_id, db):
        return {
            "items": [{"manga_id": 1, "title": "gen", "score": 0.9}],
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_gen, raising=True)

    r1 = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r1.status_code == 200, r1.text

    # invalidate hook should delete cache key
    async def fake_invalidate(user_id, collection_id):
        await fake_cache.delete(f"recommendations:{user_id}:{collection_id}")

    monkeypatch.setattr(col_routes_real, "invalidate_collection_recommendations", fake_invalidate, raising=True)
    monkeypatch.setattr(inv, "invalidate_collection_recommendations", fake_invalidate, raising=True)

    # remove manga -> should invalidate
    rem = await async_client.request(
    "DELETE",
    f"/collections/{cid}/mangas",
    json={"manga_id": manga1.manga_id},
)
    assert rem.status_code == 200, rem.text

    assert len(fake_cache.delete_calls) == 1, fake_cache.delete_calls

@pytest.mark.asyncio
async def test_update_collection_invalidates_recommendations(async_client, db_session, monkeypatch):
    manga1 = await make_manga(db_session)

    c = await async_client.post("/collections/", json={"collection_name": "InvRename", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    add1 = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga1.manga_id})
    assert add1.status_code == 200, add1.text

    fake_cache = FakeRedis()
    monkeypatch.setattr(rec_routes, "redis_cache", fake_cache, raising=True)

    async def fake_gen(user_id, collection_id, db):
        return {
            "items": [{"manga_id": 1, "title": "gen", "score": 0.9}],
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
        }

    monkeypatch.setattr(rec_routes, "generate_recommendations_for_collection", fake_gen, raising=True)

    r1 = await async_client.get(f"/recommendations/{cid}?page=1&size=20")
    assert r1.status_code == 200, r1.text
    assert len(fake_cache.set_calls) == 1

    # force invalidation to hit our FakeRedis
    async def fake_invalidate(user_id, collection_id):
        await fake_cache.delete(f"recommendations:{user_id}:{collection_id}")

    monkeypatch.setattr(col_routes_real, "invalidate_collection_recommendations", fake_invalidate, raising=True)
    monkeypatch.setattr(inv, "invalidate_collection_recommendations", fake_invalidate, raising=True)

    upd = await async_client.put(f"/collections/{cid}", json={"collection_name": "InvRename2"})
    assert upd.status_code == 200, upd.text

    assert len(fake_cache.delete_calls) == 1, fake_cache.delete_calls