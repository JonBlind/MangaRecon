from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal
import json
import uuid

import pytest

from backend.repositories import recommendation_repo
from backend.utils.domain_exceptions import NotFoundError


@pytest.mark.asyncio
async def test_assert_owned_collection_returns_none_when_owned(
    monkeypatch,
):
    user_id = uuid.uuid4()

    get_owned = AsyncMock(
        return_value=12
    )

    monkeypatch.setattr(
        recommendation_repo,
        "get_owned_collection_id",
        get_owned,
    )

    db = MagicMock()

    result = await recommendation_repo.assert_owned_collection(
        db,
        user_id=user_id,
        collection_id=12,
    )

    assert result is None

    get_owned.assert_awaited_once_with(
        db,
        user_id=user_id,
        collection_id=12,
    )


@pytest.mark.asyncio
async def test_assert_owned_collection_raises_when_missing(
    monkeypatch,
):
    user_id = uuid.uuid4()

    get_owned = AsyncMock(
        return_value=None
    )

    monkeypatch.setattr(
        recommendation_repo,
        "get_owned_collection_id",
        get_owned,
    )

    db = MagicMock()

    with pytest.raises(NotFoundError) as exc_info:
        await recommendation_repo.assert_owned_collection(
            db,
            user_id=user_id,
            collection_id=99,
        )

    error = exc_info.value

    assert error.code == "COLLECTION_NOT_FOUND"
    assert error.message == "Collection not found."

    get_owned.assert_awaited_once_with(
        db,
        user_id=user_id,
        collection_id=99,
    )


@pytest.mark.asyncio
async def test_assert_owned_collection_propagates_repository_error(
    monkeypatch,
):
    get_owned = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )

    monkeypatch.setattr(
        recommendation_repo,
        "get_owned_collection_id",
        get_owned,
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        await recommendation_repo.assert_owned_collection(
            MagicMock(),
            user_id=uuid.uuid4(),
            collection_id=10,
        )


def test_build_recommendations_cache_key():
    user_id = uuid.uuid4()

    result = recommendation_repo.build_recommendations_cache_key(
        user_id=user_id,
        collection_id=42,
    )

    assert result == (
        f"recommendations:{user_id}:42"
    )


def test_build_recommendations_cache_key_preserves_string_user_id():
    result = recommendation_repo.build_recommendations_cache_key(
        user_id="user-123",
        collection_id=7,
    )

    assert result == (
        "recommendations:user-123:7"
    )


@pytest.mark.asyncio
async def test_recommendation_cache_round_trip_preserves_payload():
    payload = {
        "items": [
            {
                "manga_id": 1,
                "title": "Berserk",
                "external_average_rating": Decimal("9.10"),
                "score": 9.5,
            }
        ],
        "seed_total": 6,
        "seed_used": 6,
        "seed_truncated": False,
    }
    cache = MagicMock()
    cache.set = AsyncMock()

    await recommendation_repo.cache_set_recommendations(
        cache,
        cache_key="recommendations:user:5",
        payload=payload,
    )

    encoded = cache.set.await_args.args[1]
    assert encoded.startswith("z1:")

    cache.get = AsyncMock(return_value=encoded)
    result = await recommendation_repo.cache_get_recommendations(
        cache,
        cache_key="recommendations:user:5",
    )

    assert result == {
        "items": [
            {
                "manga_id": 1,
                "title": "Berserk",
                "external_average_rating": 9.1,
                "score": 9.5,
            }
        ],
        "seed_total": 6,
        "seed_used": 6,
        "seed_truncated": False,
    }
    cache.get.assert_awaited_once_with("recommendations:user:5")


def test_recommendation_cache_compresses_large_payload():
    payload = {
        "items": [
            {
                "manga_id": manga_id,
                "title": f"Manga {manga_id}",
                "external_average_rating": 8.25,
                "cover_image_url": f"https://example.com/covers/{manga_id}.jpg",
                "score": 42.5,
                "details": {
                    "genre_score": 10,
                    "tag_score": 15,
                    "demo_score": 2.5,
                    "creator_score": 3,
                    "rating_score": 4,
                    "year_score": 4,
                },
            }
            for manga_id in range(1, 1_001)
        ],
        "seed_total": 6,
        "seed_used": 6,
        "seed_truncated": False,
    }

    encoded = recommendation_repo._encode_recommendations_cache(payload)
    uncompressed = json.dumps(payload, default=str)

    assert len(encoded) < len(uncompressed) * 0.25


@pytest.mark.asyncio
async def test_cache_get_recommendations_returns_none_for_cache_miss():
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)

    result = await recommendation_repo.cache_get_recommendations(
        cache,
        cache_key="missing",
    )

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_recommendations_treats_legacy_item_list_as_miss():
    cache = MagicMock()
    cache.get = AsyncMock(return_value=[{"manga_id": 1}])

    result = await recommendation_repo.cache_get_recommendations(
        cache,
        cache_key="legacy",
    )

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_recommendations_treats_malformed_payload_as_miss():
    cache = MagicMock()
    cache.get = AsyncMock(return_value="z1:not-valid-base64")

    result = await recommendation_repo.cache_get_recommendations(
        cache,
        cache_key="malformed",
    )

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_recommendations_rejects_incomplete_envelope():
    encoded = recommendation_repo._encode_recommendations_cache(
        {"items": []}
    )
    cache = MagicMock()
    cache.get = AsyncMock(return_value=encoded)

    result = await recommendation_repo.cache_get_recommendations(
        cache,
        cache_key="invalid-envelope",
    )

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_recommendations_propagates_cache_error():
    cache = MagicMock()
    cache.get = AsyncMock(
        side_effect=RuntimeError("cache unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="cache unavailable",
    ):
        await recommendation_repo.cache_get_recommendations(
            cache,
            cache_key="key",
        )


@pytest.mark.asyncio
async def test_cache_set_recommendations_accepts_empty_items():
    cache = MagicMock()
    cache.set = AsyncMock()
    payload = {
        "items": [],
        "seed_total": 1,
        "seed_used": 1,
        "seed_truncated": False,
    }

    result = await recommendation_repo.cache_set_recommendations(
        cache,
        cache_key="recommendations:user:5",
        payload=payload,
    )

    assert result is None
    encoded = cache.set.await_args.args[1]
    assert recommendation_repo._decode_recommendations_cache(encoded) == payload


@pytest.mark.asyncio
async def test_cache_set_recommendations_propagates_cache_error():
    cache = MagicMock()
    cache.set = AsyncMock(
        side_effect=RuntimeError("cache unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="cache unavailable",
    ):
        await recommendation_repo.cache_set_recommendations(
            cache,
            cache_key="key",
            payload={"items": []},
        )
