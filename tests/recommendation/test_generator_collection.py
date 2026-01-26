import pytest
import uuid


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_empty_raises(monkeypatch):
    import backend.recommendation.generator as gen
    import backend.recommendation.core as core

    class _DB:
        pass

    db = _DB()
    user_id = uuid.uuid4()
    collection_id = 123

    async def fake_get_ids(u, cid, db):
        return []

    monkeypatch.setattr(core, "get_manga_ids_in_user_collection", fake_get_ids, raising=True)

    with pytest.raises(ValueError):
        await gen.generate_recommendations_for_collection(user_id, collection_id, db)


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_calls_core_pipeline(monkeypatch):
    import backend.recommendation.generator as gen
    import backend.recommendation.core as core

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
        return {"genres": {1: 1.0}, "tags": {}, "demographics": {}}

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

    out = await gen.generate_recommendations_for_collection(user_id, collection_id, db)

    assert calls == {"ids": 1, "profile": 1, "candidates": 1, "scored": 1}
    assert out["items"][0]["manga_id"] == 99
    assert out["seed_total"] == 3
    assert out["seed_used"] == 3
    assert out["seed_truncated"] is False


@pytest.mark.asyncio
async def test_generate_recommendations_for_collection_truncates_seeds(monkeypatch):
    import backend.recommendation.generator as gen
    import backend.recommendation.core as core
    from backend.config.limits import MAX_RECOMMENDATION_SEEDS

    class _DB:
        pass

    db = _DB()
    user_id = uuid.uuid4()
    collection_id = 123

    async def fake_get_ids(u, cid, db):
        return list(range(MAX_RECOMMENDATION_SEEDS + 10))

    async def fake_profile(manga_ids, db):
        assert len(manga_ids) == MAX_RECOMMENDATION_SEEDS
        return {"genres": {}, "tags": {}, "demographics": {}}

    async def fake_candidates(*, excluded_ids, genre_ids, tag_ids, demo_ids, db):
        assert len(excluded_ids) == MAX_RECOMMENDATION_SEEDS
        return []

    async def fake_scored(candidates, metadata_profile, db):
        return []

    monkeypatch.setattr(core, "get_manga_ids_in_user_collection", fake_get_ids, raising=True)
    monkeypatch.setattr(core, "get_metadata_profile_for_collection", fake_profile, raising=True)
    monkeypatch.setattr(core, "get_candidate_manga", fake_candidates, raising=True)
    monkeypatch.setattr(core, "get_scored_recommendations", fake_scored, raising=True)

    out = await gen.generate_recommendations_for_collection(user_id, collection_id, db)

    assert out["seed_total"] == MAX_RECOMMENDATION_SEEDS + 10
    assert out["seed_used"] == MAX_RECOMMENDATION_SEEDS
    assert out["seed_truncated"] is True
