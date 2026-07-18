import inspect
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import rating_routes
from backend.schemas.rating import RatingCreate


def handler(function):
    return inspect.unwrap(function)


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def payload():
    return RatingCreate(
        manga_id=25,
        personal_rating=Decimal("8.5"),
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "expected_message",
        "needs_manga_db",
    ),
    [
        (
            "rate_manga",
            "create_or_update_rating",
            "Rating successfully submitted",
            True,
        ),
        (
            "update_rating",
            "update_existing_rating",
            "Rating updated successfully",
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_rating_write_routes_forward_payload(
    monkeypatch,
    user,
    payload,
    route_name,
    service_name,
    expected_message,
    needs_manga_db,
):
    user_db = MagicMock()
    manga_db = MagicMock()

    validated = {
        "manga_id": 25,
        "personal_rating": 8.5,
    }

    service = AsyncMock(return_value=validated)
    monkeypatch.setattr(
        rating_routes,
        service_name,
        service,
    )

    route_kwargs = {
        "request": MagicMock(),
        "rating_data": payload,
        "user_db": user_db,
        "user": user,
    }

    if needs_manga_db:
        route_kwargs["manga_db"] = manga_db

    result = await handler(
        getattr(rating_routes, route_name)
    )(**route_kwargs)

    expected_service_kwargs = {
        "user_id": user.id,
        "payload": payload,
        "user_db": user_db,
    }

    if needs_manga_db:
        expected_service_kwargs["manga_db"] = manga_db

    service.assert_awaited_once_with(
        **expected_service_kwargs
    )

    assert result["data"] == validated
    assert result["message"] == expected_message


@pytest.mark.asyncio
async def test_delete_rating_forwards_manga_id(
    monkeypatch,
    user,
):
    db = MagicMock()
    output = {"manga_id": 25}

    service = AsyncMock(return_value=output)
    monkeypatch.setattr(
        rating_routes,
        "delete_user_rating_for_manga",
        service,
    )

    result = await handler(
        rating_routes.delete_rating
    )(
        request=MagicMock(),
        manga_id=25,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        manga_id=25,
        user_db=db,
    )

    assert result["data"] == output
    assert result["message"] == (
        "Rating deleted successfully."
    )


@pytest.mark.asyncio
async def test_get_user_ratings_uses_single_rating_service_when_id_given(
    monkeypatch,
    user,
):
    db = MagicMock()
    single = {
        "manga_id": 25,
        "personal_rating": 8.5,
    }

    get_single = AsyncMock(return_value=single)
    get_page = AsyncMock()

    monkeypatch.setattr(
        rating_routes,
        "get_single_user_rating",
        get_single,
    )
    monkeypatch.setattr(
        rating_routes,
        "get_user_ratings_page",
        get_page,
    )

    result = await handler(
        rating_routes.get_user_ratings
    )(
        request=MagicMock(),
        manga_id=25,
        page=3,
        size=5,
        db=db,
        user=user,
    )

    get_single.assert_awaited_once_with(
        user_id=user.id,
        manga_id=25,
        user_db=db,
    )
    get_page.assert_not_awaited()

    assert result["data"] == single
    assert result["message"] == (
        "Rating retrieved successfully"
    )


@pytest.mark.asyncio
async def test_get_user_ratings_uses_page_service_without_id(
    monkeypatch,
    user,
):
    db = MagicMock()
    page_data = {
        "total_results": 3,
        "page": 2,
        "size": 5,
        "items": [],
    }

    get_single = AsyncMock()
    get_page = AsyncMock(return_value=page_data)

    monkeypatch.setattr(
        rating_routes,
        "get_single_user_rating",
        get_single,
    )
    monkeypatch.setattr(
        rating_routes,
        "get_user_ratings_page",
        get_page,
    )

    result = await handler(
        rating_routes.get_user_ratings
    )(
        request=MagicMock(),
        manga_id=None,
        page=2,
        size=5,
        db=db,
        user=user,
    )

    get_single.assert_not_awaited()
    get_page.assert_awaited_once_with(
        user_id=user.id,
        page=2,
        size=5,
        user_db=db,
    )

    assert result["data"] == page_data
    assert result["message"] == (
        "Ratings retrieved successfully"
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "kwargs_factory",
    ),
    [
        (
            "rate_manga",
            "create_or_update_rating",
            lambda user, payload: {
                "request": MagicMock(),
                "rating_data": payload,
                "user_db": MagicMock(),
                "manga_db": MagicMock(),
                "user": user,
            },
        ),
        (
            "update_rating",
            "update_existing_rating",
            lambda user, payload: {
                "request": MagicMock(),
                "rating_data": payload,
                "user_db": MagicMock(),
                "user": user,
            },
        ),
        (
            "delete_rating",
            "delete_user_rating_for_manga",
            lambda user, payload: {
                "request": MagicMock(),
                "manga_id": payload.manga_id,
                "db": MagicMock(),
                "user": user,
            },
        ),
        (
            "get_user_ratings",
            "get_single_user_rating",
            lambda user, payload: {
                "request": MagicMock(),
                "manga_id": payload.manga_id,
                "page": 1,
                "size": 20,
                "db": MagicMock(),
                "user": user,
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_rating_routes_propagate_service_errors(
    monkeypatch,
    user,
    payload,
    route_name,
    service_name,
    kwargs_factory,
):
    monkeypatch.setattr(
        rating_routes,
        service_name,
        AsyncMock(
            side_effect=RuntimeError(
                "rating service failed"
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="rating service failed",
    ):
        await handler(
            getattr(rating_routes, route_name)
        )(**kwargs_factory(user, payload))