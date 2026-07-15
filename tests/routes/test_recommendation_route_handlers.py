import inspect
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import recommendation_routes
from backend.schemas.recommendation import (
    RecommendationQueryListRequest,
)


def handler(function):
    return inspect.unwrap(function)


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.mark.asyncio
async def test_collection_recommendation_route_forwards_all_dependencies(
    monkeypatch,
    user,
):
    user_db = MagicMock()
    manga_db = MagicMock()
    redis_cache = MagicMock()

    data = {
        "total_results": 2,
        "page": 2,
        "size": 5,
        "items": [],
    }

    service = AsyncMock(return_value=data)
    monkeypatch.setattr(
        recommendation_routes,
        "get_recommendations_for_collection_page",
        service,
    )

    result = await handler(
        recommendation_routes.get_recommendations_for_collection
    )(
        request=MagicMock(),
        collection_id=10,
        order_by="title",
        order_dir="asc",
        page=2,
        size=5,
        user_db=user_db,
        manga_db=manga_db,
        user=user,
        redis_cache=redis_cache,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=10,
        order_by="title",
        order_dir="asc",
        page=2,
        size=5,
        user_db=user_db,
        manga_db=manga_db,
        redis_cache=redis_cache,
    )

    assert result == {
        "status": "success",
        "data": data,
        "message": (
            "Recommendations generated successfully"
        ),
        "detail": None,
    }


@pytest.mark.asyncio
async def test_query_list_recommendation_route_forwards_payload(
    monkeypatch,
):
    db = MagicMock()
    payload = RecommendationQueryListRequest(
        manga_ids=[5, 2, 5],
    )

    data = {
        "seed_total": 2,
        "seed_used": 2,
        "seed_truncated": False,
        "total_results": 0,
        "page": 3,
        "size": 10,
        "items": [],
    }

    service = AsyncMock(return_value=data)
    monkeypatch.setattr(
        recommendation_routes,
        "get_recommendations_for_query_list_page",
        service,
    )

    result = await handler(
        recommendation_routes.get_recommendations_for_query_list
    )(
        request=MagicMock(),
        payload=payload,
        order_by="external_average_rating",
        order_dir="desc",
        page=3,
        size=10,
        db=db,
    )

    service.assert_awaited_once_with(
        manga_ids=[5, 2, 5],
        order_by="external_average_rating",
        order_dir="desc",
        page=3,
        size=10,
        db=db,
    )

    assert result["data"] == data
    assert result["message"] == (
        "Recommendations generated successfully"
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "kwargs",
    ),
    [
        (
            "get_recommendations_for_collection",
            "get_recommendations_for_collection_page",
            {
                "request": MagicMock(),
                "collection_id": 10,
                "order_by": "score",
                "order_dir": "desc",
                "page": 1,
                "size": 20,
                "user_db": MagicMock(),
                "manga_db": MagicMock(),
                "user": SimpleNamespace(
                    id=uuid.uuid4()
                ),
                "redis_cache": MagicMock(),
            },
        ),
        (
            "get_recommendations_for_query_list",
            "get_recommendations_for_query_list_page",
            {
                "request": MagicMock(),
                "payload": RecommendationQueryListRequest(
                    manga_ids=[1]
                ),
                "order_by": "score",
                "order_dir": "desc",
                "page": 1,
                "size": 20,
                "db": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_recommendation_routes_propagate_service_errors(
    monkeypatch,
    route_name,
    service_name,
    kwargs,
):
    monkeypatch.setattr(
        recommendation_routes,
        service_name,
        AsyncMock(
            side_effect=RuntimeError(
                "recommendation failed"
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="recommendation failed",
    ):
        await handler(
            getattr(
                recommendation_routes,
                route_name,
            )
        )(**kwargs)