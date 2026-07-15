from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services import recommendation_service
from backend.utils.domain_exceptions import BadRequestError


def make_items():
    return [
        {
            "manga_id": 1,
            "title": "Berserk",
            "score": 9.5,
            "external_average_rating": 9.1,
        },
        {
            "manga_id": 2,
            "title": "Monster",
            "score": 8.5,
            "external_average_rating": 8.8,
        },
        {
            "manga_id": 3,
            "title": "Akira",
            "score": 8.5,
            "external_average_rating": None,
        },
    ]


def test_sort_items_by_score_descending():
    items = make_items()

    recommendation_service._sort_items(
        items,
        order_by="score",
        order_dir="desc",
    )

    assert [item["title"] for item in items] == [
        "Berserk",
        "Monster",
        "Akira",
    ]


def test_sort_items_by_score_ascending():
    items = make_items()

    recommendation_service._sort_items(
        items,
        order_by="score",
        order_dir="asc",
    )

    assert [item["title"] for item in items] == [
        "Akira",
        "Monster",
        "Berserk",
    ]


def test_sort_items_uses_title_as_tiebreaker():
    items = [
        {
            "title": "Zulu",
            "score": 5,
        },
        {
            "title": "Alpha",
            "score": 5,
        },
    ]

    recommendation_service._sort_items(
        items,
        order_by="score",
        order_dir="asc",
    )

    assert [item["title"] for item in items] == [
        "Alpha",
        "Zulu",
    ]


def test_sort_items_by_title_case_insensitive():
    items = [
        {
            "title": "monster",
            "score": 1,
        },
        {
            "title": "Akira",
            "score": 1,
        },
        {
            "title": "berserk",
            "score": 1,
        },
    ]

    recommendation_service._sort_items(
        items,
        order_by="title",
        order_dir="asc",
    )

    assert [item["title"] for item in items] == [
        "Akira",
        "berserk",
        "monster",
    ]


def test_sort_items_treats_missing_title_as_empty_string():
    items = [
        {
            "manga_id": 1,
            "title": None,
        },
        {
            "manga_id": 2,
            "title": "Berserk",
        },
        {
            "manga_id": 3,
        },
    ]

    recommendation_service._sort_items(
        items,
        order_by="title",
        order_dir="asc",
    )

    assert [item.get("manga_id") for item in items] == [
        1,
        3,
        2,
    ]


def test_sort_items_by_generic_field():
    items = make_items()

    recommendation_service._sort_items(
        items,
        order_by="external_average_rating",
        order_dir="desc",
    )

    assert [item["title"] for item in items] == [
        "Berserk",
        "Monster",
        "Akira",
    ]


def test_sort_items_places_missing_generic_value_first_ascending():
    items = make_items()

    recommendation_service._sort_items(
        items,
        order_by="external_average_rating",
        order_dir="asc",
    )

    assert items[0]["title"] == "Akira"


def test_sort_items_handles_missing_score():
    items = [
        {
            "title": "Missing Score",
        },
        {
            "title": "Rated",
            "score": 4.0,
        },
    ]

    recommendation_service._sort_items(
        items,
        order_by="score",
        order_dir="asc",
    )

    assert [item["title"] for item in items] == [
        "Missing Score",
        "Rated",
    ]


@pytest.mark.asyncio
async def test_collection_recommendations_cache_hit(
    monkeypatch,
):
    user_id = "user-1"
    user_db = MagicMock()
    manga_db = MagicMock()
    redis_cache = MagicMock()

    items = make_items()

    assert_owned = AsyncMock()
    build_key = MagicMock(
        return_value="recommendations:user-1:10"
    )
    cache_get = AsyncMock(
        return_value=items
    )
    cache_set = AsyncMock()
    generator = AsyncMock()

    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        assert_owned,
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        build_key,
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        cache_get,
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_set_items",
        cache_set,
    )
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_collection",
        generator,
    )

    result = await recommendation_service.get_recommendations_for_collection_page(
        user_id=user_id,
        collection_id=10,
        order_by="title",
        order_dir="asc",
        page=1,
        size=2,
        user_db=user_db,
        manga_db=manga_db,
        redis_cache=redis_cache,
    )

    assert_owned.assert_awaited_once_with(
        user_db,
        user_id=user_id,
        collection_id=10,
    )
    build_key.assert_called_once_with(
        user_id=user_id,
        collection_id=10,
    )
    cache_get.assert_awaited_once_with(
        redis_cache,
        cache_key="recommendations:user-1:10",
    )

    generator.assert_not_awaited()
    cache_set.assert_not_awaited()

    assert result == {
        "total_results": 3,
        "page": 1,
        "size": 2,
        "items": [
            {
                "manga_id": 3,
                "title": "Akira",
                "score": 8.5,
                "external_average_rating": None,
            },
            {
                "manga_id": 1,
                "title": "Berserk",
                "score": 9.5,
                "external_average_rating": 9.1,
            },
        ],
    }


@pytest.mark.asyncio
async def test_collection_recommendations_cache_miss_generates_and_caches(
    monkeypatch,
):
    user_id = "user-1"
    user_db = MagicMock()
    manga_db = MagicMock()
    redis_cache = MagicMock()

    generated_items = make_items()

    assert_owned = AsyncMock()
    build_key = MagicMock(
        return_value="recommendations:user-1:10"
    )
    cache_get = AsyncMock(
        return_value=None
    )
    cache_set = AsyncMock()
    generator = AsyncMock(
        return_value={
            "items": generated_items,
            "seed_total": 20,
            "seed_used": 15,
            "seed_truncated": True,
        }
    )

    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        assert_owned,
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        build_key,
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        cache_get,
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_set_items",
        cache_set,
    )
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_collection",
        generator,
    )

    result = await recommendation_service.get_recommendations_for_collection_page(
        user_id=user_id,
        collection_id=10,
        order_by="score",
        order_dir="desc",
        page=1,
        size=2,
        user_db=user_db,
        manga_db=manga_db,
        redis_cache=redis_cache,
    )

    generator.assert_awaited_once_with(
        user_id,
        10,
        user_db,
        manga_db,
    )

    cache_set.assert_awaited_once_with(
        redis_cache,
        cache_key="recommendations:user-1:10",
        items=generated_items,
    )

    assert result == {
        "total_results": 3,
        "page": 1,
        "size": 2,
        "items": [
            {
                "manga_id": 1,
                "title": "Berserk",
                "score": 9.5,
                "external_average_rating": 9.1,
            },
            {
                "manga_id": 2,
                "title": "Monster",
                "score": 8.5,
                "external_average_rating": 8.8,
            },
        ],
        "seed_total": 20,
        "seed_used": 15,
        "seed_truncated": True,
    }


@pytest.mark.asyncio
async def test_collection_recommendations_omits_seed_metadata_when_generator_does_not_return_it(
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        MagicMock(return_value="key"),
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_set_items",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_collection",
        AsyncMock(
            return_value={
                "items": [],
            }
        ),
    )

    result = await recommendation_service.get_recommendations_for_collection_page(
        user_id="user-1",
        collection_id=10,
        order_by="score",
        order_dir="desc",
        page=1,
        size=20,
        user_db=MagicMock(),
        manga_db=MagicMock(),
        redis_cache=MagicMock(),
    )

    assert result == {
        "total_results": 0,
        "page": 1,
        "size": 20,
        "items": [],
    }

    assert "seed_total" not in result
    assert "seed_used" not in result
    assert "seed_truncated" not in result


@pytest.mark.asyncio
async def test_collection_recommendations_returns_later_page(
    monkeypatch,
):
    items = [
        {
            "title": f"Manga {index}",
            "score": index,
        }
        for index in range(1, 7)
    ]

    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        MagicMock(return_value="key"),
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        AsyncMock(return_value=items),
    )

    result = await recommendation_service.get_recommendations_for_collection_page(
        user_id="user",
        collection_id=1,
        order_by="score",
        order_dir="asc",
        page=2,
        size=2,
        user_db=MagicMock(),
        manga_db=MagicMock(),
        redis_cache=MagicMock(),
    )

    assert result["total_results"] == 6
    assert result["page"] == 2
    assert result["size"] == 2
    assert [item["score"] for item in result["items"]] == [
        3,
        4,
    ]


@pytest.mark.asyncio
async def test_collection_recommendations_returns_empty_out_of_range_page(
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        MagicMock(return_value="key"),
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        AsyncMock(return_value=make_items()),
    )

    result = await recommendation_service.get_recommendations_for_collection_page(
        user_id="user",
        collection_id=1,
        order_by="score",
        order_dir="desc",
        page=50,
        size=10,
        user_db=MagicMock(),
        manga_db=MagicMock(),
        redis_cache=MagicMock(),
    )

    assert result["total_results"] == 3
    assert result["items"] == []


@pytest.mark.asyncio
async def test_collection_recommendations_propagates_ownership_error(
    monkeypatch,
):
    assert_owned = AsyncMock(
        side_effect=RuntimeError("ownership failed")
    )

    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        assert_owned,
    )

    with pytest.raises(
        RuntimeError,
        match="ownership failed",
    ):
        await recommendation_service.get_recommendations_for_collection_page(
            user_id="user",
            collection_id=1,
            order_by="score",
            order_dir="desc",
            page=1,
            size=10,
            user_db=MagicMock(),
            manga_db=MagicMock(),
            redis_cache=MagicMock(),
        )


@pytest.mark.asyncio
async def test_collection_recommendations_propagates_generator_error(
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "assert_owned_collection",
        AsyncMock(),
    )
    monkeypatch.setattr(
        recommendation_service,
        "build_recommendations_cache_key",
        MagicMock(return_value="key"),
    )
    monkeypatch.setattr(
        recommendation_service,
        "cache_get_items",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_collection",
        AsyncMock(
            side_effect=RuntimeError("generation failed")
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        await recommendation_service.get_recommendations_for_collection_page(
            user_id="user",
            collection_id=1,
            order_by="score",
            order_dir="desc",
            page=1,
            size=10,
            user_db=MagicMock(),
            manga_db=MagicMock(),
            redis_cache=MagicMock(),
        )


@pytest.mark.asyncio
async def test_query_list_rejects_empty_seed_list():
    with pytest.raises(BadRequestError) as exc_info:
        await recommendation_service.get_recommendations_for_query_list_page(
            manga_ids=[],
            order_by="score",
            order_dir="desc",
            page=1,
            size=20,
            db=MagicMock(),
        )

    error = exc_info.value

    assert error.code == "RECOMMENDATION_SEED_EMPTY"
    assert error.message == (
        "Need at least 1 manga in the list to "
        "generate recommendations."
    )


@pytest.mark.asyncio
async def test_query_list_deduplicates_preserving_order(
    monkeypatch,
):
    db = MagicMock()

    generator = AsyncMock(
        return_value={
            "items": [],
            "seed_total": 3,
            "seed_used": 3,
            "seed_truncated": False,
        }
    )

    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_list",
        generator,
    )

    result = await recommendation_service.get_recommendations_for_query_list_page(
        manga_ids=[
            5,
            2,
            5,
            7,
            2,
        ],
        order_by="score",
        order_dir="desc",
        page=1,
        size=20,
        db=db,
    )

    generator.assert_awaited_once_with(
        [5, 2, 7],
        db,
    )

    assert result["seed_total"] == 3
    assert result["seed_used"] == 3
    assert result["seed_truncated"] is False


@pytest.mark.asyncio
async def test_query_list_sorts_and_paginates_results(
    monkeypatch,
):
    items = make_items()

    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_list",
        AsyncMock(
            return_value={
                "items": items,
                "seed_total": 4,
                "seed_used": 4,
                "seed_truncated": False,
            }
        ),
    )

    result = await recommendation_service.get_recommendations_for_query_list_page(
        manga_ids=[1, 2, 3, 4],
        order_by="title",
        order_dir="asc",
        page=2,
        size=1,
        db=MagicMock(),
    )

    assert result == {
        "seed_total": 4,
        "seed_used": 4,
        "seed_truncated": False,
        "total_results": 3,
        "page": 2,
        "size": 1,
        "items": [
            {
                "manga_id": 1,
                "title": "Berserk",
                "score": 9.5,
                "external_average_rating": 9.1,
            }
        ],
    }


@pytest.mark.asyncio
async def test_query_list_returns_empty_out_of_range_page(
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_list",
        AsyncMock(
            return_value={
                "items": make_items(),
                "seed_total": 2,
                "seed_used": 2,
                "seed_truncated": False,
            }
        ),
    )

    result = await recommendation_service.get_recommendations_for_query_list_page(
        manga_ids=[1, 2],
        order_by="score",
        order_dir="desc",
        page=20,
        size=10,
        db=MagicMock(),
    )

    assert result["total_results"] == 3
    assert result["items"] == []


@pytest.mark.asyncio
async def test_query_list_propagates_generator_error(
    monkeypatch,
):
    monkeypatch.setattr(
        recommendation_service,
        "generate_recommendations_for_list",
        AsyncMock(
            side_effect=RuntimeError("generation failed")
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="generation failed",
    ):
        await recommendation_service.get_recommendations_for_query_list_page(
            manga_ids=[1],
            order_by="score",
            order_dir="desc",
            page=1,
            size=20,
            db=MagicMock(),
        )