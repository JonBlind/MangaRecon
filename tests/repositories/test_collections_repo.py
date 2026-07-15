from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.repositories import collections_repo


class FakeResult:
    def __init__(
        self,
        *,
        scalar_value=None,
        scalar_rows=None,
    ):
        self.scalar_value = scalar_value
        self.scalar_rows = scalar_rows or []

    def scalar_one_or_none(self):
        return self.scalar_value

    def scalar_one(self):
        return self.scalar_value

    def scalars(self):
        return self

    def all(self):
        return self.scalar_rows


@pytest.mark.asyncio
async def test_get_owned_collection_id_returns_collection_id():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=12,
        )
    )

    user_id = uuid.uuid4()

    result = await collections_repo.get_owned_collection_id(
        db,
        user_id=user_id,
        collection_id=12,
    )

    assert result == 12
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_owned_collection_id_returns_none_when_not_owned():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=None,
        )
    )

    result = await collections_repo.get_owned_collection_id(
        db,
        user_id=uuid.uuid4(),
        collection_id=999,
    )

    assert result is None
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_collection_manga_returns_count():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=7,
        )
    )

    result = await collections_repo.count_collection_manga(
        db,
        collection_id=4,
    )

    assert result == 7
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_collection_manga_returns_zero():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=0,
        )
    )

    result = await collections_repo.count_collection_manga(
        db,
        collection_id=4,
    )

    assert result == 0


@pytest.mark.asyncio
async def test_page_collection_manga_ids_returns_ascending_page():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=[10, 20, 30],
        )
    )

    result = await collections_repo.page_collection_manga_ids(
        db,
        collection_id=5,
        offset=0,
        limit=3,
        order="asc",
    )

    assert result == [10, 20, 30]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_page_collection_manga_ids_returns_descending_page():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=[30, 20, 10],
        )
    )

    result = await collections_repo.page_collection_manga_ids(
        db,
        collection_id=5,
        offset=3,
        limit=3,
        order="desc",
    )

    assert result == [30, 20, 10]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_page_collection_manga_ids_returns_empty_list():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=[],
        )
    )

    result = await collections_repo.page_collection_manga_ids(
        db,
        collection_id=5,
        offset=20,
        limit=10,
        order="asc",
    )

    assert result == []