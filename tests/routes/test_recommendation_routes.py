import pytest

from tests.db.factories import make_manga
from backend.routes import recommendation_routes as rec_routes

class FakeRedis:
    def __init__(self):
        self.store = {}
        self.get_calls = []
        self.set_calls = []

    async def get(self, key: str):
        self.get_calls.append(key)
        return self.store.get(key)

    async def set(self, key: str, value):
        self.set_calls.append((key, value))
        self.store[key] = value


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
    import backend.routes.recommendation_routes as rec_routes

    collection_id = await _create_collection(async_client)
    fake_redis = FakeRedis()

    # prime cache with deterministic list
    # NOTE: cache_key format matches your route
    user_id = "TEST_USER_ID"  # only used in key; your override user has some id
    # We can’t easily read the overridden user id here, so we patch the route cache key usage indirectly:
    # easiest: just patch redis_cache.get/set and accept “some key” is used.
    cached = [
        {"manga_id": 1, "title": "B", "score": 0.0},
        {"manga_id": 2, "title": "A", "score": 9.5},
    ]

    async def fake_get(key):
        return cached

    async def fake_set(key, val):
        raise AssertionError("set should not be called on cache hit")

    fake_redis.get = fake_get
    fake_redis.set = fake_set

    async def generator_should_not_run(*args, **kwargs):
        raise AssertionError("generate_recommendations should not be called on cache hit")

    monkeypatch.setattr(rec_routes, "redis_cache", fake_redis, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations", generator_should_not_run, raising=True)

    resp = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=1&size=20")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["items"][0]["score"] == 9.5


@pytest.mark.asyncio
async def test_recommendations_cache_miss_sets_cache_and_second_call_hits(async_client, monkeypatch):
    import backend.routes.recommendation_routes as rec_routes

    collection_id = await _create_collection(async_client)
    fake_redis = FakeRedis()

    calls = {"gen": 0}
    generated = [
        {"manga_id": 1, "title": "Z", "score": 1.0},
        {"manga_id": 2, "title": "A", "score": 10.0},
    ]

    async def fake_generate(*args, **kwargs):
        calls["gen"] += 1
        return list(generated)

    monkeypatch.setattr(rec_routes, "redis_cache", fake_redis, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations", fake_generate, raising=True)

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
async def test_recommendations_sorting_and_pagination(async_client, monkeypatch):
    import backend.routes.recommendation_routes as rec_routes

    collection_id = await _create_collection(async_client)
    fake_redis = FakeRedis()

    # intentionally messy ordering and edge values (0.0 must not be treated as missing)
    generated = [
        {"manga_id": 1, "title": "bbb", "score": 0.0},
        {"manga_id": 2, "title": "aaa", "score": 0.0},
        {"manga_id": 3, "title": "ccc", "score": 5.0},
        {"manga_id": 4, "title": None, "score": 9.0},
    ]

    async def fake_generate(*args, **kwargs):
        return list(generated)

    monkeypatch.setattr(rec_routes, "redis_cache", fake_redis, raising=True)
    monkeypatch.setattr(rec_routes, "generate_recommendations", fake_generate, raising=True)

    # score desc => 9.0 first, then 5.0, then 0.0s (tie-broken by title)
    resp = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=1&size=2")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert [items[0]["score"], items[1]["score"]] == [9.0, 5.0]

    # page 2 should contain the 0.0s
    resp2 = await async_client.get(f"/recommendations/{collection_id}?order_by=score&order_dir=desc&page=2&size=2")
    assert resp2.status_code == 200, resp2.text
    items2 = resp2.json()["data"]["items"]
    assert all(x["score"] == 0.0 for x in items2)
    assert [x["title"] for x in items2] == ["bbb", "aaa"] or [x["title"] for x in items2] == ["aaa", "bbb"]

    # title asc => None treated as "" so should come first
    resp3 = await async_client.get(f"/recommendations/{collection_id}?order_by=title&order_dir=asc&page=1&size=20")
    assert resp3.status_code == 200, resp3.text
    items3 = resp3.json()["data"]["items"]
    assert items3[0]["title"] is None

@pytest.mark.asyncio
async def test_recommendations_missing_collection_404(async_client):
    resp = await async_client.get("/recommendations/999999?page=1&size=20")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_recommendations_sort_and_paginate(async_client, monkeypatch):
    # 1) create a collection
    c = await async_client.post("/collections/", json={"collection_name": "RecTest", "description": "d"})
    cid = c.json()["data"]["collection_id"]

    # 2) monkeypatch generator to return deterministic data
    fake = [
        {"manga_id": 1, "title": "Bleach", "score": 0.2},
        {"manga_id": 2, "title": "Attack on Titan", "score": 0.9},
        {"manga_id": 3, "title": "Chainsaw Man", "score": 0.9},
        {"manga_id": 4, "title": "Naruto", "score": 0.1},
    ]

    async def _fake_gen(user_id, collection_id, session):
        return list(fake)

    monkeypatch.setattr(rec_routes, "generate_recommendations", _fake_gen)

    # 3) call with ordering by score desc, size=2
    r1 = await async_client.get(f"/recommendations/{cid}?order_by=score&order_dir=desc&page=1&size=2")
    assert r1.status_code == 200, r1.text
    items = r1.json()["data"]["items"]
    assert len(items) == 2
    # top scores should be 0.9, tie broken by title casefold in your code
    assert items[0]["score"] == 0.9
    assert items[1]["score"] == 0.9

    # page 2 should continue
    r2 = await async_client.get(f"/recommendations/{cid}?order_by=score&order_dir=desc&page=2&size=2")
    assert r2.status_code == 200, r2.text
    items2 = r2.json()["data"]["items"]
    assert len(items2) == 2
    assert {i["manga_id"] for i in items2} == {1, 4}