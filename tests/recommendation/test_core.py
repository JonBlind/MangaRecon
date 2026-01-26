import pytest
import uuid

from backend.config.limits import MAX_RECOMMENDATION_SEEDS
from backend.recommendation.generator import (
    generate_recommendations_for_collection,
    generate_recommendations_for_list,
)
import backend.recommendation.core as core


@pytest.mark.asyncio
async def test_generate_recommendations_for_list_empty_raises():
    class _DB:
        pass

    with pytest.raises(ValueError):
        await generate_recommendations_for_list([], _DB())


@pytest.mark.asyncio
async def test_generate_recommendations_for_list_calls_core_pipeline(monkeypatch):
    class _DB:
        pass

    db = _DB()
    calls = {"profile": 0, "candidates": 0, "scored": 0}
    captured = {}

    async def fake_profile(manga_ids, db):
        calls["profile"] += 1
        captured["manga_ids"] = manga_ids
        return {"genres": {1: 0.7, 2: 0.3}, "tags": {10: 1.0}, "demographics": {5: 1.0}, "authors": set(), "external_ratings": [], "years": []}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        calls["candidates"] += 1
        captured["excluded_ids"] = excluded_ids
        captured["genre_ids"] = genre_ids
        captured["tag_ids"] = tag_ids
        captured["demo_ids"] = demo_ids
        return [{"manga_id": 99, "title": "Candidate"}]

    async def fake_scored(candidates, metadata_profile, db):
        calls["scored"] += 1
        assert candidates == [{"manga_id": 99, "title": "Candidate"}]
        assert "genres" in metadata_profile
        return [{"manga_id": 99, "title": "Candidate", "score": 0.9}]

    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    out = await generate_recommendations_for_list([1, 2, 3], db)

    assert calls == {"profile": 1, "candidates": 1, "scored": 1}
    assert captured["manga_ids"] == [1, 2, 3]
    assert captured["excluded_ids"] == [1, 2, 3]
    assert set(captured["genre_ids"]) == {1, 2}
    assert set(captured["tag_ids"]) == {10}
    assert set(captured["demo_ids"]) == {5}

    assert out["items"] == [{"manga_id": 99, "title": "Candidate", "score": 0.9}]
    assert out["seed_total"] == 3
    assert out["seed_used"] == 3
    assert out["seed_truncated"] is False


@pytest.mark.asyncio
async def test_generate_recommendations_for_list_truncates_seeds(monkeypatch):
    class _DB:
        pass

    db = _DB()
    long_list = list(range(1, MAX_RECOMMENDATION_SEEDS + 25 + 1))

    async def fake_profile(manga_ids, db):
        assert len(manga_ids) == MAX_RECOMMENDATION_SEEDS
        return {"genres": {}, "tags": {}, "demographics": {}, "authors": set(), "external_ratings": [], "years": []}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        assert len(excluded_ids) == MAX_RECOMMENDATION_SEEDS
        return [{"manga_id": 999, "title": "X"}]

    async def fake_scored(candidates, metadata_profile, db):
        return [{"manga_id": 999, "title": "X", "score": 1.0}]

    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    out = await generate_recommendations_for_list(long_list, db)

    assert out["seed_total"] == len(long_list)
    assert out["seed_used"] == MAX_RECOMMENDATION_SEEDS
    assert out["seed_truncated"] is True
    assert out["items"][0]["manga_id"] == 999


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_empty_raises(monkeypatch):
    class _DB:
        pass

    db = _DB()
    user_id = uuid.uuid4()
    collection_id = 123

    async def fake_get_ids(u, cid, db):
        return []

    monkeypatch.setattr(core, "get_manga_ids_in_user_collection", fake_get_ids, raising=True)

    with pytest.raises(ValueError):
        await generate_recommendations_for_collection(user_id, collection_id, db)


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_calls_core_pipeline(monkeypatch):
    class _DB:
        pass

    db = _DB()
    user_id = uuid.uuid4()
    collection_id = 123

    calls = {"ids": 0, "profile": 0, "candidates": 0, "scored": 0}

    async def fake_get_ids(u, cid, db):
        calls["ids"] += 1
        assert u == user_id
        assert cid == collection_id
        return [1, 2, 3]

    async def fake_profile(manga_ids, db):
        calls["profile"] += 1
        assert manga_ids == [1, 2, 3]
        return {"genres": {1: 1.0}, "tags": {}, "demographics": {}, "authors": set(), "external_ratings": [], "years": []}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        calls["candidates"] += 1
        assert excluded_ids == [1, 2, 3]
        assert genre_ids == [1]
        assert tag_ids == []
        assert demo_ids == []
        return [{"manga_id": 99, "title": "Candidate"}]

    async def fake_scored(candidates, metadata_profile, db):
        calls["scored"] += 1
        return [{"manga_id": 99, "title": "Candidate", "score": 0.5}]

    monkeypatch.setattr(core, "get_manga_ids_in_user_collection", fake_get_ids, raising=True)
    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    out = await generate_recommendations_for_collection(user_id, collection_id, db)

    assert calls == {"ids": 1, "profile": 1, "candidates": 1, "scored": 1}
    assert out["items"][0]["manga_id"] == 99
    assert out["seed_total"] == 3
    assert out["seed_used"] == 3
    assert out["seed_truncated"] is False


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_truncates_seeds(monkeypatch):
    class _DB:
        pass

    db = _DB()
    user_id = uuid.uuid4()
    collection_id = 123

    async def fake_get_ids(u, cid, db):
        return list(range(MAX_RECOMMENDATION_SEEDS + 10))

    async def fake_profile(manga_ids, db):
        assert len(manga_ids) == MAX_RECOMMENDATION_SEEDS
        return {"genres": {}, "tags": {}, "demographics": {}, "authors": set(), "external_ratings": [], "years": []}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        assert len(excluded_ids) == MAX_RECOMMENDATION_SEEDS
        return []

    async def fake_scored(candidates, metadata_profile, db):
        return []

    monkeypatch.setattr(core, "get_manga_ids_in_user_collection", fake_get_ids, raising=True)
    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    out = await generate_recommendations_for_collection(user_id, collection_id, db)

    assert out["seed_total"] == MAX_RECOMMENDATION_SEEDS + 10
    assert out["seed_used"] == MAX_RECOMMENDATION_SEEDS
    assert out["seed_truncated"] is True
