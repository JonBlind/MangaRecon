import inspect
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import collection_routes
from backend.schemas.collection import (
    BulkMangaInCollectionRequest,
    CollectionCreate,
    CollectionUpdate,
    MangaInCollectionRequest,
)
from backend.utils.domain_exceptions import NotFoundError


def handler(function):
    return inspect.unwrap(function)


@pytest.fixture
def user():
    return SimpleNamespace(id=uuid.uuid4())


@pytest.fixture
def fake_request():
    return MagicMock()


@pytest.mark.asyncio
async def test_get_users_collection_forwards_parameters(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    service = AsyncMock(
        return_value={
            "total_results": 1,
            "page": 2,
            "size": 5,
            "items": [{"collection_id": 10}],
        }
    )

    monkeypatch.setattr(
        collection_routes,
        "list_user_collections_page",
        service,
    )

    result = await handler(
        collection_routes.get_users_collection
    )(
        request=fake_request,
        page=2,
        size=5,
        order="asc",
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        page=2,
        size=5,
        order="asc",
        user_db=db,
    )

    assert result == {
        "status": "success",
        "data": {
            "total_results": 1,
            "page": 2,
            "size": 5,
            "items": [{"collection_id": 10}],
        },
        "message": "Collections retrieved",
        "detail": None,
    }


@pytest.mark.asyncio
async def test_get_collection_by_id_forwards_parameters(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    collection = {
        "collection_id": 12,
        "collection_name": "Favorites",
    }

    service = AsyncMock(return_value=collection)
    monkeypatch.setattr(
        collection_routes,
        "get_user_collection_by_id",
        service,
    )

    result = await handler(
        collection_routes.get_collection_by_id
    )(
        request=fake_request,
        collection_id=12,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=12,
        user_db=db,
    )

    assert result["data"] == collection
    assert result["message"] == (
        "Collection retrieved successfully"
    )


@pytest.mark.asyncio
async def test_create_collection_forwards_payload(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    payload = CollectionCreate(
        collection_name="Favorites",
        description="Favorite manga",
    )

    created = {
        "collection_id": 5,
        "collection_name": "Favorites",
    }

    service = AsyncMock(return_value=created)
    monkeypatch.setattr(
        collection_routes,
        "create_user_collection",
        service,
    )

    result = await handler(
        collection_routes.create_collection
    )(
        request=fake_request,
        collection_data=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        payload=payload,
        user_db=db,
    )

    assert result["data"] == created
    assert result["message"] == (
        "Collection created successfully"
    )


@pytest.mark.asyncio
async def test_update_collection_forwards_payload(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    payload = CollectionUpdate(
        collection_name="Updated",
    )

    updated = {
        "collection_id": 5,
        "collection_name": "Updated",
    }

    service = AsyncMock(return_value=updated)
    monkeypatch.setattr(
        collection_routes,
        "update_user_collection",
        service,
    )

    result = await handler(
        collection_routes.update_collection
    )(
        request=fake_request,
        collection_id=5,
        collection_update=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=5,
        payload=payload,
        user_db=db,
    )

    assert result["data"] == updated
    assert result["message"] == (
        "Collection updated successfully"
    )


@pytest.mark.asyncio
async def test_delete_collection_forwards_parameters(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    deleted = {"collection_id": 5}

    service = AsyncMock(return_value=deleted)
    monkeypatch.setattr(
        collection_routes,
        "delete_user_collection",
        service,
    )

    result = await handler(
        collection_routes.delete_collection
    )(
        request=fake_request,
        collection_id=5,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=5,
        user_db=db,
    )

    assert result["data"] == deleted
    assert result["message"] == (
        "Collection deleted successfully"
    )


@pytest.mark.asyncio
async def test_get_collection_manga_forwards_both_databases(
    monkeypatch,
    fake_request,
    user,
):
    user_db = MagicMock()
    manga_db = MagicMock()

    page_data = {
        "total_results": 2,
        "page": 2,
        "size": 10,
        "items": [],
    }

    service = AsyncMock(return_value=page_data)
    monkeypatch.setattr(
        collection_routes,
        "get_collection_manga_page",
        service,
    )

    result = await handler(
        collection_routes.get_manga_in_collection
    )(
        request=fake_request,
        collection_id=7,
        page=2,
        size=10,
        order="asc",
        user_db=user_db,
        manga_db=manga_db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=7,
        page=2,
        size=10,
        order="asc",
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result["data"] == page_data
    assert result["message"] == (
        "Manga retrieved successfully"
    )


@pytest.mark.asyncio
async def test_bulk_add_forwards_all_manga_ids(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    payload = BulkMangaInCollectionRequest(
        manga_ids=[1, 2, 3],
    )

    output = {
        "collection_id": 7,
        "added_count": 3,
        "failed_count": 0,
        "added_ids": [1, 2, 3],
        "failed": [],
    }

    service = AsyncMock(return_value=output)
    monkeypatch.setattr(
        collection_routes,
        "add_manga_bulk_to_user_collection",
        service,
    )

    result = await handler(
        collection_routes.add_manga_bulk_to_collection
    )(
        request=fake_request,
        collection_id=7,
        data=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=7,
        manga_ids=[1, 2, 3],
        user_db=db,
    )

    assert result["data"] == output
    assert result["message"] == (
        "Manga bulk add completed"
    )


@pytest.mark.asyncio
async def test_add_single_manga_forwards_id(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    payload = MangaInCollectionRequest(
        manga_id=25,
    )

    output = {
        "collection_id": 7,
        "manga_id": 25,
    }

    service = AsyncMock(return_value=output)
    monkeypatch.setattr(
        collection_routes,
        "add_manga_to_user_collection",
        service,
    )

    result = await handler(
        collection_routes.add_manga_to_collection
    )(
        request=fake_request,
        collection_id=7,
        data=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=7,
        manga_id=25,
        user_db=db,
    )

    assert result["data"] == output
    assert result["message"] == (
        "Manga added to collection"
    )


@pytest.mark.asyncio
async def test_remove_single_manga_forwards_id(
    monkeypatch,
    fake_request,
    user,
):
    db = MagicMock()
    payload = MangaInCollectionRequest(
        manga_id=25,
    )

    output = {
        "collection_id": 7,
        "manga_id": 25,
    }

    service = AsyncMock(return_value=output)
    monkeypatch.setattr(
        collection_routes,
        "remove_manga_from_user_collection",
        service,
    )

    result = await handler(
        collection_routes.remove_manga_from_collection
    )(
        request=fake_request,
        collection_id=7,
        data=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        collection_id=7,
        manga_id=25,
        user_db=db,
    )

    assert result["data"] == output
    assert result["message"] == (
        "Manga removed from collection"
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "extra_kwargs",
    ),
    [
        (
            "get_users_collection",
            "list_user_collections_page",
            {
                "page": 1,
                "size": 20,
                "order": "desc",
                "db": MagicMock(),
            },
        ),
        (
            "get_collection_by_id",
            "get_user_collection_by_id",
            {
                "collection_id": 5,
                "db": MagicMock(),
            },
        ),
        (
            "create_collection",
            "create_user_collection",
            {
                "collection_data": CollectionCreate(
                    collection_name="Favorites"
                ),
                "db": MagicMock(),
            },
        ),
        (
            "update_collection",
            "update_user_collection",
            {
                "collection_id": 5,
                "collection_update": CollectionUpdate(
                    collection_name="Updated"
                ),
                "db": MagicMock(),
            },
        ),
        (
            "delete_collection",
            "delete_user_collection",
            {
                "collection_id": 5,
                "db": MagicMock(),
            },
        ),
        (
            "get_manga_in_collection",
            "get_collection_manga_page",
            {
                "collection_id": 5,
                "page": 1,
                "size": 20,
                "order": "desc",
                "user_db": MagicMock(),
                "manga_db": MagicMock(),
            },
        ),
        (
            "add_manga_bulk_to_collection",
            "add_manga_bulk_to_user_collection",
            {
                "collection_id": 5,
                "data": BulkMangaInCollectionRequest(
                    manga_ids=[1, 2]
                ),
                "db": MagicMock(),
            },
        ),
        (
            "add_manga_to_collection",
            "add_manga_to_user_collection",
            {
                "collection_id": 5,
                "data": MangaInCollectionRequest(
                    manga_id=10
                ),
                "db": MagicMock(),
            },
        ),
        (
            "remove_manga_from_collection",
            "remove_manga_from_user_collection",
            {
                "collection_id": 5,
                "data": MangaInCollectionRequest(
                    manga_id=10
                ),
                "db": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_collection_routes_reraise_domain_errors(
    monkeypatch,
    fake_request,
    user,
    route_name,
    service_name,
    extra_kwargs,
):
    domain_error = NotFoundError(
        code="COLLECTION_NOT_FOUND",
        message="Collection not found.",
    )

    monkeypatch.setattr(
        collection_routes,
        service_name,
        AsyncMock(side_effect=domain_error),
    )

    route = handler(
        getattr(collection_routes, route_name)
    )

    with pytest.raises(NotFoundError) as exc_info:
        await route(
            request=fake_request,
            user=user,
            **extra_kwargs,
        )

    assert exc_info.value is domain_error


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "extra_kwargs",
    ),
    [
        (
            "get_users_collection",
            "list_user_collections_page",
            {
                "page": 1,
                "size": 20,
                "order": "desc",
                "db": MagicMock(),
            },
        ),
        (
            "get_collection_by_id",
            "get_user_collection_by_id",
            {
                "collection_id": 5,
                "db": MagicMock(),
            },
        ),
        (
            "create_collection",
            "create_user_collection",
            {
                "collection_data": CollectionCreate(
                    collection_name="Favorites"
                ),
                "db": MagicMock(),
            },
        ),
        (
            "update_collection",
            "update_user_collection",
            {
                "collection_id": 5,
                "collection_update": CollectionUpdate(
                    collection_name="Updated"
                ),
                "db": MagicMock(),
            },
        ),
        (
            "delete_collection",
            "delete_user_collection",
            {
                "collection_id": 5,
                "db": MagicMock(),
            },
        ),
        (
            "get_manga_in_collection",
            "get_collection_manga_page",
            {
                "collection_id": 5,
                "page": 1,
                "size": 20,
                "order": "desc",
                "user_db": MagicMock(),
                "manga_db": MagicMock(),
            },
        ),
        (
            "add_manga_bulk_to_collection",
            "add_manga_bulk_to_user_collection",
            {
                "collection_id": 5,
                "data": BulkMangaInCollectionRequest(
                    manga_ids=[1, 2]
                ),
                "db": MagicMock(),
            },
        ),
        (
            "add_manga_to_collection",
            "add_manga_to_user_collection",
            {
                "collection_id": 5,
                "data": MangaInCollectionRequest(
                    manga_id=10
                ),
                "db": MagicMock(),
            },
        ),
        (
            "remove_manga_from_collection",
            "remove_manga_from_user_collection",
            {
                "collection_id": 5,
                "data": MangaInCollectionRequest(
                    manga_id=10
                ),
                "db": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_collection_routes_log_and_reraise_unexpected_errors(
    monkeypatch,
    fake_request,
    user,
    route_name,
    service_name,
    extra_kwargs,
):
    failure = RuntimeError("service failed")
    log_error = MagicMock()

    monkeypatch.setattr(
        collection_routes,
        service_name,
        AsyncMock(side_effect=failure),
    )
    monkeypatch.setattr(
        collection_routes.logger,
        "error",
        log_error,
    )

    route = handler(
        getattr(collection_routes, route_name)
    )

    with pytest.raises(
        RuntimeError,
        match="service failed",
    ):
        await route(
            request=fake_request,
            user=user,
            **extra_kwargs,
        )

    log_error.assert_called_once()
    assert (
        log_error.call_args.kwargs["exc_info"]
        is True
    )