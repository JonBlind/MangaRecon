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
@pytest.mark.parametrize(
    ("order", "expected_ids"),
    [
        ("asc", [10, 20, 30]),
        ("desc", [30, 20, 10]),
    ],
)
async def test_list_collection_manga_ids_returns_stable_order(
    order,
    expected_ids,
):
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=expected_ids,
        )
    )

    result = await collections_repo.list_collection_manga_ids(
        db,
        collection_id=5,
        order=order,
    )

    assert result == expected_ids
    statement = db.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)
    expected_direction = "ASC" if order == "asc" else "DESC"

    assert "manga_collection.collection_id" in sql
    assert f"ORDER BY manga_collection.manga_id {expected_direction}" in sql
    assert "LIMIT" not in sql
    assert "OFFSET" not in sql
    assert 5 in compiled.params.values()
