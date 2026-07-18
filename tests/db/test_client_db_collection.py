from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.db import client_db
from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)
from backend.utils.domain_exceptions import (
    ConflictError,
    NotFoundError,
)


@pytest.fixture
def session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


def scalar_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def scalar_list_result(values):
    scalars = MagicMock()
    scalars.all.return_value = values

    result = MagicMock()
    result.scalars.return_value = scalars

    return result


@pytest.mark.asyncio
async def test_get_manga_in_collection_returns_manga_rows(
    session,
):
    user_id = uuid.uuid4()
    collection = MagicMock()
    manga_rows = [MagicMock(), MagicMock()]

    session.execute.side_effect = [
        scalar_result(collection),
        scalar_list_result(manga_rows),
    ]

    db = ClientReadDatabase(session)

    result = await db.get_manga_in_collection(
        user_id,
        10,
    )

    assert result == manga_rows
    assert session.execute.await_count == 2

    ownership_stmt = session.execute.await_args_list[0].args[0]
    manga_stmt = session.execute.await_args_list[1].args[0]

    ownership_compiled = ownership_stmt.compile()
    manga_compiled = manga_stmt.compile()

    assert "collection.collection_id" in str(ownership_stmt)
    assert "collection.user_id" in str(ownership_stmt)
    assert user_id in ownership_compiled.params.values()
    assert 10 in ownership_compiled.params.values()

    assert "JOIN manga_collection" in str(manga_stmt)
    assert 10 in manga_compiled.params.values()


@pytest.mark.asyncio
async def test_get_manga_in_collection_raises_when_collection_missing(
    session,
):
    session.execute.return_value = scalar_result(None)

    db = ClientReadDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.get_manga_in_collection(
            uuid.uuid4(),
            10,
        )

    assert exc_info.value.code == "COLLECTION_NOT_FOUND"
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_get_manga_in_collection_logs_and_reraises_database_error(
    monkeypatch,
    session,
):
    session.execute.side_effect = SQLAlchemyError(
        "query failed"
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientReadDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="query failed",
    ):
        await db.get_manga_in_collection(
            uuid.uuid4(),
            10,
        )

    log_error.assert_called_once()
    assert log_error.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_is_manga_in_collection_returns_true_when_link_exists(
    session,
):
    session.execute.return_value = scalar_result(
        MagicMock()
    )

    db = ClientReadDatabase(session)

    result = await db.is_manga_in_collection(
        10,
        25,
    )

    assert result is True


@pytest.mark.asyncio
async def test_is_manga_in_collection_returns_false_when_missing(
    session,
):
    session.execute.return_value = scalar_result(None)

    db = ClientReadDatabase(session)

    result = await db.is_manga_in_collection(
        10,
        25,
    )

    assert result is False


@pytest.mark.asyncio
async def test_is_manga_in_collection_returns_false_on_database_error(
    monkeypatch,
    session,
):
    session.execute.side_effect = SQLAlchemyError(
        "query failed"
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientReadDatabase(session)

    result = await db.is_manga_in_collection(
        10,
        25,
    )

    assert result is False
    log_error.assert_called_once()


@pytest.mark.asyncio
async def test_add_manga_to_collection_adds_link_and_commits(
    session,
):
    user_id = uuid.uuid4()
    collection = MagicMock()

    session.execute.side_effect = [
        scalar_result(collection),
        scalar_result(None),
    ]

    db = ClientWriteDatabase(session)

    result = await db.add_manga_to_collection(
        user_id,
        10,
        25,
    )

    assert result is None

    session.add.assert_called_once()

    added_link = session.add.call_args.args[0]

    assert isinstance(
        added_link,
        client_db.MangaCollection,
    )
    assert added_link.collection_id == 10
    assert added_link.manga_id == 25

    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_manga_to_collection_raises_when_collection_missing(
    session,
):
    session.execute.return_value = scalar_result(None)

    db = ClientWriteDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.add_manga_to_collection(
            uuid.uuid4(),
            10,
            25,
        )

    assert exc_info.value.code == "COLLECTION_NOT_FOUND"

    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()

@pytest.mark.asyncio
async def test_add_manga_to_collection_raises_when_link_already_exists(
    session,
):
    session.execute.side_effect = [
        scalar_result(MagicMock()),
        scalar_result(MagicMock()),
        scalar_result(MagicMock()),
    ]

    db = ClientWriteDatabase(session)

    with pytest.raises(ConflictError) as exc_info:
        await db.add_manga_to_collection(
            uuid.uuid4(),
            10,
            25,
        )

    error = exc_info.value

    assert error.code == "COLLECTION_MANGA_CONFLICT"
    assert error.detail == {
        "collection_id": 10,
        "manga_id": 25,
    }

    session.add.assert_not_called()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_manga_to_collection_rolls_back_on_commit_error(
    session,
):
    session.execute.side_effect = [
        scalar_result(MagicMock()),
        scalar_result(None),
    ]

    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="commit failed",
    ):
        await db.add_manga_to_collection(
            uuid.uuid4(),
            10,
            25,
        )

    session.add.assert_called_once()
    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_deletes_link_and_commits(
    session,
):
    collection = MagicMock()
    link = MagicMock()

    session.execute.side_effect = [
        scalar_result(collection),
        scalar_result(link),
    ]

    db = ClientWriteDatabase(session)

    result = await db.remove_manga_from_collection(
        uuid.uuid4(),
        10,
        25,
    )

    assert result is None

    session.delete.assert_awaited_once_with(link)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_raises_when_collection_missing(
    session,
):
    session.execute.return_value = scalar_result(None)

    db = ClientWriteDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.remove_manga_from_collection(
            uuid.uuid4(),
            10,
            25,
        )

    assert exc_info.value.code == "COLLECTION_NOT_FOUND"

    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_raises_when_link_missing(
    session,
):
    session.execute.side_effect = [
        scalar_result(MagicMock()),
        scalar_result(None),
    ]

    db = ClientWriteDatabase(session)

    with pytest.raises(NotFoundError) as exc_info:
        await db.remove_manga_from_collection(
            uuid.uuid4(),
            10,
            25,
        )

    assert exc_info.value.code == (
        "COLLECTION_MANGA_NOT_FOUND"
    )

    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_rolls_back_on_delete_error(
    session,
):
    link = MagicMock()

    session.execute.side_effect = [
        scalar_result(MagicMock()),
        scalar_result(link),
    ]

    session.delete.side_effect = SQLAlchemyError(
        "delete failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="delete failed",
    ):
        await db.remove_manga_from_collection(
            uuid.uuid4(),
            10,
            25,
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_manga_from_collection_rolls_back_on_commit_error(
    session,
):
    link = MagicMock()

    session.execute.side_effect = [
        scalar_result(MagicMock()),
        scalar_result(link),
    ]

    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="commit failed",
    ):
        await db.remove_manga_from_collection(
            uuid.uuid4(),
            10,
            25,
        )

    session.delete.assert_awaited_once_with(link)
    session.rollback.assert_awaited_once_with()