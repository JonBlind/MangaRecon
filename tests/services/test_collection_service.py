from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.db.models.collection import Collection
from backend.schemas.collection import (
    CollectionCreate,
    CollectionUpdate,
)
from backend.services import collection_service
from backend.utils.domain_exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
)


class FakeResult:
    def __init__(
        self,
        *,
        scalar_value=None,
        scalar_rows=None,
    ):
        self.scalar_value = scalar_value
        self.scalar_rows = scalar_rows or []

    def scalar_one(self):
        return self.scalar_value

    def scalar_one_or_none(self):
        return self.scalar_value

    def scalars(self):
        return self

    def all(self):
        return self.scalar_rows


def make_collection(
    *,
    collection_id=1,
    user_id=None,
    collection_name="Favorites",
    description="My favorite manga",
):
    return Collection(
        collection_id=collection_id,
        user_id=user_id or uuid.uuid4(),
        collection_name=collection_name,
        description=description,
        created_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )


def make_write_db():
    db = MagicMock()

    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.delete = AsyncMock()

    db.add_manga_to_collection = AsyncMock()
    db.remove_manga_from_collection = AsyncMock()

    return db


@pytest.mark.asyncio
async def test_list_user_collections_page_returns_paginated_items():
    user_id = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            FakeResult(scalar_value=2),
            FakeResult(
                scalar_rows=[
                    make_collection(
                        collection_id=1,
                        user_id=user_id,
                        collection_name="First",
                    ),
                    make_collection(
                        collection_id=2,
                        user_id=user_id,
                        collection_name="Second",
                    ),
                ]
            ),
        ]
    )

    result = await collection_service.list_user_collections_page(
        user_id=user_id,
        page=1,
        size=10,
        order="asc",
        user_db=db,
    )

    assert result["total_results"] == 2
    assert result["page"] == 1
    assert result["size"] == 10
    assert [
        item.collection_id
        for item in result["items"]
    ] == [1, 2]
    assert [
        item.collection_name
        for item in result["items"]
    ] == [
        "First",
        "Second",
    ]
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_user_collections_page_supports_descending_order():
    db = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            FakeResult(scalar_value=0),
            FakeResult(scalar_rows=[]),
        ]
    )

    result = await collection_service.list_user_collections_page(
        user_id=uuid.uuid4(),
        page=2,
        size=5,
        order="desc",
        user_db=db,
    )

    assert result == {
        "total_results": 0,
        "page": 2,
        "size": 5,
        "items": [],
    }


@pytest.mark.asyncio
async def test_get_user_collection_by_id_returns_collection():
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id
    )

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=collection
        )
    )

    result = await collection_service.get_user_collection_by_id(
        user_id=user_id,
        collection_id=1,
        user_db=db,
    )

    assert result.collection_id == 1
    assert result.collection_name == "Favorites"
    assert result.description == "My favorite manga"


@pytest.mark.asyncio
async def test_get_user_collection_by_id_raises_when_missing():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=None
        )
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.get_user_collection_by_id(
            user_id=uuid.uuid4(),
            collection_id=999,
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NOT_FOUND"
    )
    assert (
        exc_info.value.message
        == "Collection not found."
    )


@pytest.mark.asyncio
async def test_create_user_collection_commits_and_returns_collection():
    user_id = uuid.uuid4()
    db = make_write_db()

    async def fake_refresh(collection):
        collection.collection_id = 12
        collection.created_at = datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )

    db.refresh.side_effect = fake_refresh

    payload = CollectionCreate(
        collection_name="Completed",
        description="Finished manga",
    )

    result = await collection_service.create_user_collection(
        user_id=user_id,
        payload=payload,
        user_db=db,
    )

    db.add.assert_called_once()

    added_collection = db.add.call_args.args[0]

    assert added_collection.user_id == user_id
    assert (
        added_collection.collection_name
        == "Completed"
    )
    assert (
        added_collection.description
        == "Finished manga"
    )

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(
        added_collection
    )
    db.rollback.assert_not_awaited()

    assert result.collection_id == 12
    assert result.collection_name == "Completed"


@pytest.mark.asyncio
async def test_create_user_collection_converts_integrity_error_to_conflict():
    db = make_write_db()
    db.commit.side_effect = IntegrityError(
        "INSERT",
        {},
        Exception("duplicate"),
    )

    with pytest.raises(ConflictError) as exc_info:
        await collection_service.create_user_collection(
            user_id=uuid.uuid4(),
            payload=CollectionCreate(
                collection_name="Duplicate",
                description=None,
            ),
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NAME_CONFLICT"
    )
    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_user_collection_rolls_back_unexpected_error():
    db = make_write_db()
    db.commit.side_effect = RuntimeError(
        "database unavailable"
    )

    with pytest.raises(
        RuntimeError,
        match="database unavailable",
    ):
        await collection_service.create_user_collection(
            user_id=uuid.uuid4(),
            payload=CollectionCreate(
                collection_name="Favorites",
                description=None,
            ),
            user_db=db,
        )

    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_collection_updates_fields_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id,
        collection_name="Old Name",
        description="Old description",
    )

    db = make_write_db()
    db.execute.side_effect = [
        FakeResult(
            scalar_value=collection
        ),
        FakeResult(
            scalar_value=None
        ),
    ]

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.update_user_collection(
        user_id=user_id,
        collection_id=1,
        payload=CollectionUpdate(
            collection_name="New Name",
            description="New description",
        ),
        user_db=db,
    )

    assert (
        collection.collection_name
        == "New Name"
    )
    assert (
        collection.description
        == "New description"
    )

    assert result.collection_name == "New Name"
    assert (
        result.description
        == "New description"
    )

    assert db.execute.await_count == 2
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(
        collection
    )
    db.rollback.assert_not_awaited()

    invalidate.assert_awaited_once_with(
        user_id,
        1,
    )


@pytest.mark.asyncio
async def test_update_user_collection_allows_description_only_update(
    monkeypatch,
):
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id,
        collection_name="Unchanged",
        description="Old",
    )

    db = make_write_db()
    db.execute.return_value = FakeResult(
        scalar_value=collection
    )

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.update_user_collection(
        user_id=user_id,
        collection_id=1,
        payload=CollectionUpdate(
            description="Updated"
        ),
        user_db=db,
    )

    assert (
        collection.collection_name
        == "Unchanged"
    )
    assert collection.description == "Updated"
    assert result.description == "Updated"

    db.execute.assert_awaited_once()
    invalidate.assert_awaited_once_with(
        user_id,
        1,
    )


@pytest.mark.asyncio
async def test_update_user_collection_raises_when_collection_missing():
    db = make_write_db()
    db.execute.return_value = FakeResult(
        scalar_value=None
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.update_user_collection(
            user_id=uuid.uuid4(),
            collection_id=999,
            payload=CollectionUpdate(
                description="Updated"
            ),
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NOT_FOUND"
    )
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_collection_rejects_duplicate_name():
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id,
        collection_name="Old",
    )

    db = make_write_db()
    db.execute.side_effect = [
        FakeResult(
            scalar_value=collection
        ),
        FakeResult(
            scalar_value=88
        ),
    ]

    with pytest.raises(ConflictError) as exc_info:
        await collection_service.update_user_collection(
            user_id=user_id,
            collection_id=1,
            payload=CollectionUpdate(
                collection_name="Already Used"
            ),
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NAME_CONFLICT"
    )
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_user_collection_converts_integrity_error_to_conflict(
    monkeypatch,
):
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id
    )

    db = make_write_db()
    db.execute.side_effect = [
        FakeResult(
            scalar_value=collection
        ),
        FakeResult(
            scalar_value=None
        ),
    ]
    db.commit.side_effect = IntegrityError(
        "UPDATE",
        {},
        Exception("duplicate"),
    )

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    with pytest.raises(ConflictError) as exc_info:
        await collection_service.update_user_collection(
            user_id=user_id,
            collection_id=1,
            payload=CollectionUpdate(
                collection_name="Duplicate"
            ),
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NAME_CONFLICT"
    )
    db.rollback.assert_awaited_once()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_collection_deletes_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    collection = make_collection(
        user_id=user_id
    )

    db = make_write_db()
    db.execute.return_value = FakeResult(
        scalar_value=collection
    )

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.delete_user_collection(
        user_id=user_id,
        collection_id=1,
        user_db=db,
    )

    assert result == {
        "collection_id": 1,
    }
    db.delete.assert_awaited_once_with(
        collection
    )
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
    invalidate.assert_awaited_once_with(
        user_id,
        1,
    )


@pytest.mark.asyncio
async def test_delete_user_collection_raises_when_missing():
    db = make_write_db()
    db.execute.return_value = FakeResult(
        scalar_value=None
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.delete_user_collection(
            user_id=uuid.uuid4(),
            collection_id=999,
            user_db=db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NOT_FOUND"
    )
    db.rollback.assert_awaited_once()
    db.delete.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_collection_rolls_back_unexpected_error():
    collection = make_collection()

    db = make_write_db()
    db.execute.return_value = FakeResult(
        scalar_value=collection
    )
    db.delete.side_effect = RuntimeError(
        "delete failed"
    )

    with pytest.raises(
        RuntimeError,
        match="delete failed",
    ):
        await collection_service.delete_user_collection(
            user_id=collection.user_id,
            collection_id=1,
            user_db=db,
        )

    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_collection_manga_page_raises_when_not_owned(
    monkeypatch,
):
    get_owned = AsyncMock(
        return_value=None
    )
    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        get_owned,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.get_collection_manga_page(
            user_id=uuid.uuid4(),
            collection_id=8,
            page=1,
            size=10,
            order="asc",
            user_db=MagicMock(),
            manga_db=MagicMock(),
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NOT_FOUND"
    )


@pytest.mark.asyncio
async def test_get_collection_manga_page_returns_empty_page(
    monkeypatch,
):
    user_db = MagicMock()
    manga_db = MagicMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        AsyncMock(return_value=4),
    )
    monkeypatch.setattr(
        collection_service,
        "count_collection_manga",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        collection_service,
        "page_collection_manga_ids",
        AsyncMock(return_value=[]),
    )

    fetch_base = AsyncMock()
    attach_genres = AsyncMock()

    monkeypatch.setattr(
        collection_service,
        "fetch_manga_list_base",
        fetch_base,
    )
    monkeypatch.setattr(
        collection_service,
        "attach_genres_to_base",
        attach_genres,
    )

    result = await collection_service.get_collection_manga_page(
        user_id=uuid.uuid4(),
        collection_id=4,
        page=2,
        size=5,
        order="desc",
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result == {
        "total_results": 0,
        "page": 2,
        "size": 5,
        "items": [],
    }

    fetch_base.assert_not_awaited()
    attach_genres.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_collection_manga_page_preserves_membership_order(
    monkeypatch,
):
    user_db = MagicMock()
    manga_db = MagicMock()

    get_owned = AsyncMock(return_value=4)
    count_manga = AsyncMock(return_value=3)
    page_ids = AsyncMock(
        return_value=[30, 10, 20]
    )

    base_by_id = {
        10: {
            "manga_id": 10,
            "title": "Ten",
            "genres": [],
            "average_rating": 7.5,
            "cover_image_url": None,
        },
        20: {
            "manga_id": 20,
            "title": "Twenty",
            "genres": [],
            "average_rating": 8.0,
            "cover_image_url": "twenty.jpg",
        },
        30: {
            "manga_id": 30,
            "title": "Thirty",
            "genres": [],
            "average_rating": None,
            "cover_image_url": None,
        },
    }

    fetch_base = AsyncMock(
        return_value=base_by_id
    )
    attach_genres = AsyncMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        get_owned,
    )
    monkeypatch.setattr(
        collection_service,
        "count_collection_manga",
        count_manga,
    )
    monkeypatch.setattr(
        collection_service,
        "page_collection_manga_ids",
        page_ids,
    )
    monkeypatch.setattr(
        collection_service,
        "fetch_manga_list_base",
        fetch_base,
    )
    monkeypatch.setattr(
        collection_service,
        "attach_genres_to_base",
        attach_genres,
    )

    result = await collection_service.get_collection_manga_page(
        user_id=uuid.uuid4(),
        collection_id=4,
        page=2,
        size=3,
        order="desc",
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result["total_results"] == 3
    assert result["page"] == 2
    assert result["size"] == 3
    assert [
        item.manga_id
        for item in result["items"]
    ] == [
        30,
        10,
        20,
    ]

    page_ids.assert_awaited_once_with(
        user_db,
        collection_id=4,
        offset=3,
        limit=3,
        order="desc",
    )
    fetch_base.assert_awaited_once_with(
        manga_db,
        manga_ids=[30, 10, 20],
    )
    attach_genres.assert_awaited_once_with(
        manga_db,
        manga_ids=[30, 10, 20],
        base_by_id=base_by_id,
    )


@pytest.mark.asyncio
async def test_get_collection_manga_page_skips_missing_manga_rows(
    monkeypatch,
):
    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        AsyncMock(return_value=1),
    )
    monkeypatch.setattr(
        collection_service,
        "count_collection_manga",
        AsyncMock(return_value=2),
    )
    monkeypatch.setattr(
        collection_service,
        "page_collection_manga_ids",
        AsyncMock(
            return_value=[10, 20]
        ),
    )
    monkeypatch.setattr(
        collection_service,
        "fetch_manga_list_base",
        AsyncMock(
            return_value={
                20: {
                    "manga_id": 20,
                    "title": "Existing",
                    "genres": [],
                    "average_rating": None,
                    "cover_image_url": None,
                }
            }
        ),
    )
    monkeypatch.setattr(
        collection_service,
        "attach_genres_to_base",
        AsyncMock(),
    )

    result = await collection_service.get_collection_manga_page(
        user_id=uuid.uuid4(),
        collection_id=1,
        page=1,
        size=10,
        order="asc",
        user_db=MagicMock(),
        manga_db=MagicMock(),
    )

    assert result["total_results"] == 2
    assert [
        item.manga_id
        for item in result["items"]
    ] == [20]


@pytest.mark.asyncio
async def test_add_manga_to_collection_adds_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user_db = make_write_db()
    manga_db = MagicMock()

    manga_exists_mock = AsyncMock(
        return_value=True
    )
    invalidate = AsyncMock()

    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        manga_exists_mock,
    )
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.add_manga_to_user_collection(
        user_id=user_id,
        collection_id=10,
        manga_id=25,
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result == {
        "collection_id": 10,
        "manga_id": 25,
    }

    manga_exists_mock.assert_awaited_once_with(
        manga_db,
        manga_id=25,
    )
    user_db.add_manga_to_collection.assert_awaited_once_with(
        user_id,
        10,
        25,
    )
    invalidate.assert_awaited_once_with(
        user_id,
        10,
    )


@pytest.mark.asyncio
async def test_add_manga_rejects_missing_manga(
    monkeypatch,
):
    user_db = make_write_db()
    manga_db = MagicMock()

    manga_exists_mock = AsyncMock(
        return_value=False
    )
    invalidate = AsyncMock()

    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        manga_exists_mock,
    )
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.add_manga_to_user_collection(
            user_id=uuid.uuid4(),
            collection_id=10,
            manga_id=999,
            user_db=user_db,
            manga_db=manga_db,
        )

    assert (
        exc_info.value.code
        == "MANGA_NOT_FOUND"
    )
    assert (
        exc_info.value.message
        == "Manga not found."
    )

    user_db.add_manga_to_collection.assert_not_awaited()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_add_raises_when_collection_not_owned(
    monkeypatch,
):
    user_db = make_write_db()
    manga_db = MagicMock()

    get_owned = AsyncMock(
        return_value=None
    )
    exists = AsyncMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        get_owned,
    )
    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        exists,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await collection_service.add_manga_bulk_to_user_collection(
            user_id=uuid.uuid4(),
            collection_id=9,
            manga_ids=[1, 2],
            user_db=user_db,
            manga_db=manga_db,
        )

    assert (
        exc_info.value.code
        == "COLLECTION_NOT_FOUND"
    )

    exists.assert_not_awaited()
    user_db.add_manga_to_collection.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_add_records_successes_and_failures(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user_db = make_write_db()
    manga_db = MagicMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        AsyncMock(return_value=4),
    )

    manga_exists_mock = AsyncMock(
        side_effect=[
            True,
            True,
            True,
            True,
            False,
            True,
        ]
    )
    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        manga_exists_mock,
    )

    user_db.add_manga_to_collection.side_effect = [
        None,
        ConflictError(
            code="MANGA_ALREADY_IN_COLLECTION",
            message="Already exists.",
        ),
        NotFoundError(
            code="COLLECTION_NOT_FOUND",
            message="Collection not found.",
        ),
        DomainError(
            status_code=400,
            code="OTHER_DOMAIN_ERROR",
            message="Other error.",
        ),
        None,
    ]

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.add_manga_bulk_to_user_collection(
        user_id=user_id,
        collection_id=4,
        manga_ids=[
            10,
            20,
            30,
            40,
            45,
            50,
        ],
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result.collection_id == 4
    assert result.added_count == 2
    assert result.failed_count == 4
    assert result.added_ids == [
        10,
        50,
    ]

    assert [
        failure.model_dump()
        for failure in result.failed
    ] == [
        {
            "manga_id": 20,
            "reason": "ALREADY_EXISTS",
        },
        {
            "manga_id": 30,
            "reason": "COLLECTION_NOT_FOUND",
        },
        {
            "manga_id": 40,
            "reason": "UNKNOWN",
        },
        {
            "manga_id": 45,
            "reason": "MANGA_NOT_FOUND",
        },
    ]

    assert (
        manga_exists_mock.await_count
        == 6
    )
    assert (
        user_db.add_manga_to_collection.await_count
        == 5
    )

    user_db.add_manga_to_collection.assert_any_await(
        user_id,
        10 and 4,
        10,
    )

    invalidate.assert_awaited_once_with(
        user_id,
        4,
    )


@pytest.mark.asyncio
async def test_bulk_add_does_not_invalidate_when_all_manga_missing(
    monkeypatch,
):
    user_db = make_write_db()
    manga_db = MagicMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        AsyncMock(return_value=4),
    )

    manga_exists_mock = AsyncMock(
        return_value=False
    )
    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        manga_exists_mock,
    )

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.add_manga_bulk_to_user_collection(
        user_id=uuid.uuid4(),
        collection_id=4,
        manga_ids=[10, 20],
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result.added_count == 0
    assert result.failed_count == 2
    assert result.added_ids == []

    assert [
        failure.reason
        for failure in result.failed
    ] == [
        "MANGA_NOT_FOUND",
        "MANGA_NOT_FOUND",
    ]

    user_db.add_manga_to_collection.assert_not_awaited()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_add_does_not_invalidate_when_all_conflicts(
    monkeypatch,
):
    user_db = make_write_db()
    manga_db = MagicMock()

    monkeypatch.setattr(
        collection_service,
        "get_owned_collection_id",
        AsyncMock(return_value=4),
    )
    monkeypatch.setattr(
        collection_service,
        "manga_exists",
        AsyncMock(return_value=True),
    )

    user_db.add_manga_to_collection.side_effect = [
        ConflictError(
            code="MANGA_ALREADY_IN_COLLECTION",
            message="Already exists.",
        ),
        ConflictError(
            code="MANGA_ALREADY_IN_COLLECTION",
            message="Already exists.",
        ),
    ]

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.add_manga_bulk_to_user_collection(
        user_id=uuid.uuid4(),
        collection_id=4,
        manga_ids=[10, 20],
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result.added_count == 0
    assert result.failed_count == 2
    assert result.added_ids == []

    assert [
        failure.reason
        for failure in result.failed
    ] == [
        "ALREADY_EXISTS",
        "ALREADY_EXISTS",
    ]

    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_removes_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = make_write_db()

    invalidate = AsyncMock()
    monkeypatch.setattr(
        collection_service,
        "invalidate_collection_recommendations",
        invalidate,
    )

    result = await collection_service.remove_manga_from_user_collection(
        user_id=user_id,
        collection_id=7,
        manga_id=99,
        user_db=db,
    )

    assert result == {
        "collection_id": 7,
        "manga_id": 99,
    }

    db.remove_manga_from_collection.assert_awaited_once_with(
        user_id,
        7,
        99,
    )
    invalidate.assert_awaited_once_with(
        user_id,
        7,
    )