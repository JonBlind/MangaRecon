from unittest.mock import AsyncMock, MagicMock
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
async def test_cache_get_items_returns_cached_items():
    items = [
        {
            "manga_id": 1,
            "score": 9.5,
        },
        {
            "manga_id": 2,
            "score": 8.5,
        },
    ]

    cache = MagicMock()
    cache.get = AsyncMock(
        return_value=items
    )

    result = await recommendation_repo.cache_get_items(
        cache,
        cache_key="recommendations:user:5",
    )

    assert result == items

    cache.get.assert_awaited_once_with(
        "recommendations:user:5"
    )


@pytest.mark.asyncio
async def test_cache_get_items_returns_none_for_cache_miss():
    cache = MagicMock()
    cache.get = AsyncMock(
        return_value=None
    )

    result = await recommendation_repo.cache_get_items(
        cache,
        cache_key="missing",
    )

    assert result is None


@pytest.mark.asyncio
async def test_cache_get_items_propagates_cache_error():
    cache = MagicMock()
    cache.get = AsyncMock(
        side_effect=RuntimeError("cache unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="cache unavailable",
    ):
        await recommendation_repo.cache_get_items(
            cache,
            cache_key="key",
        )


@pytest.mark.asyncio
async def test_cache_set_items_stores_items():
    items = [
        {
            "manga_id": 1,
            "score": 9.5,
        }
    ]

    cache = MagicMock()
    cache.set = AsyncMock()

    result = await recommendation_repo.cache_set_items(
        cache,
        cache_key="recommendations:user:5",
        items=items,
    )

    assert result is None

    cache.set.assert_awaited_once_with(
        "recommendations:user:5",
        items,
    )


@pytest.mark.asyncio
async def test_cache_set_items_accepts_empty_list():
    cache = MagicMock()
    cache.set = AsyncMock()

    result = await recommendation_repo.cache_set_items(
        cache,
        cache_key="recommendations:user:5",
        items=[],
    )

    assert result is None

    cache.set.assert_awaited_once_with(
        "recommendations:user:5",
        [],
    )


@pytest.mark.asyncio
async def test_cache_set_items_propagates_cache_error():
    cache = MagicMock()
    cache.set = AsyncMock(
        side_effect=RuntimeError("cache unavailable")
    )

    with pytest.raises(
        RuntimeError,
        match="cache unavailable",
    ):
        await recommendation_repo.cache_set_items(
            cache,
            cache_key="key",
            items=[],
        )