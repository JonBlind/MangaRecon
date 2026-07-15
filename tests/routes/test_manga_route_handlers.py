import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import manga_routes


def handler(function):
    return inspect.unwrap(function)


@pytest.mark.asyncio
async def test_get_manga_by_id_forwards_arguments(
    monkeypatch,
):
    request = MagicMock()
    db = MagicMock()

    manga = {
        "manga_id": 25,
        "title": "Monster",
    }

    service = AsyncMock(return_value=manga)
    monkeypatch.setattr(
        manga_routes,
        "get_manga_detail",
        service,
    )

    result = await handler(
        manga_routes.get_manga_by_id
    )(
        request=request,
        manga_id=25,
        db=db,
    )

    service.assert_awaited_once_with(
        manga_id=25,
        db=db,
    )

    assert result == {
        "status": "success",
        "data": manga,
        "message": "Manga retrieved successfully",
        "detail": None,
    }


@pytest.mark.asyncio
async def test_filter_manga_forwards_all_filters(
    monkeypatch,
):
    request = MagicMock()
    db = MagicMock()

    page_data = {
        "total_results": 1,
        "page": 3,
        "size": 10,
        "items": [],
    }

    service = AsyncMock(return_value=page_data)
    monkeypatch.setattr(
        manga_routes,
        "filter_manga_page",
        service,
    )

    result = await handler(
        manga_routes.filter_manga
    )(
        request=request,
        genre_ids=[1, 2],
        exclude_genres=[3],
        tag_ids=[4],
        exclude_tags=[5],
        demo_ids=[6],
        exclude_demos=[7],
        title="monster",
        page=3,
        size=10,
        order_by="external_average_rating",
        order_dir="desc",
        db=db,
    )

    service.assert_awaited_once_with(
        genre_ids=[1, 2],
        exclude_genres=[3],
        tag_ids=[4],
        exclude_tags=[5],
        demo_ids=[6],
        exclude_demos=[7],
        title="monster",
        page=3,
        size=10,
        order_by="external_average_rating",
        order_dir="desc",
        db=db,
    )

    assert result["data"] == page_data
    assert result["message"] == (
        "Filtered manga retrieved successfully"
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "kwargs",
    ),
    [
        (
            "get_manga_by_id",
            "get_manga_detail",
            {
                "request": MagicMock(),
                "manga_id": 25,
                "db": MagicMock(),
            },
        ),
        (
            "filter_manga",
            "filter_manga_page",
            {
                "request": MagicMock(),
                "genre_ids": None,
                "exclude_genres": None,
                "tag_ids": None,
                "exclude_tags": None,
                "demo_ids": None,
                "exclude_demos": None,
                "title": None,
                "page": 1,
                "size": 50,
                "order_by": "title",
                "order_dir": "asc",
                "db": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_manga_routes_log_and_reraise_errors(
    monkeypatch,
    route_name,
    service_name,
    kwargs,
):
    failure = RuntimeError("manga service failed")
    log_error = MagicMock()

    monkeypatch.setattr(
        manga_routes,
        service_name,
        AsyncMock(side_effect=failure),
    )
    monkeypatch.setattr(
        manga_routes.logger,
        "error",
        log_error,
    )

    with pytest.raises(
        RuntimeError,
        match="manga service failed",
    ):
        await handler(
            getattr(manga_routes, route_name)
        )(**kwargs)

    log_error.assert_called_once()
    assert (
        log_error.call_args.kwargs["exc_info"]
        is True
    )