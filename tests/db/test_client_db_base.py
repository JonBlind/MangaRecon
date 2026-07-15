from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)
from backend.utils.domain_exceptions import BadRequestError


@pytest.fixture
def session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_execute_delegates_to_session(session):
    statement = MagicMock()
    expected_result = MagicMock()
    session.execute.return_value = expected_result

    db = ClientReadDatabase(session)

    result = await db.execute(statement)

    assert result is expected_result
    session.execute.assert_awaited_once_with(statement)


@pytest.mark.asyncio
async def test_scalar_one_or_none_executes_and_returns_scalar(session):
    statement = MagicMock()
    query_result = MagicMock()
    expected = MagicMock()

    query_result.scalar_one_or_none.return_value = expected
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.scalar_one_or_none(statement)

    assert result is expected
    session.execute.assert_awaited_once_with(statement)
    query_result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_scalar_one_or_none_returns_none(session):
    statement = MagicMock()
    query_result = MagicMock()

    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.scalar_one_or_none(statement)

    assert result is None


@pytest.mark.asyncio
async def test_scalars_all_returns_all_scalar_rows(session):
    statement = MagicMock()
    expected = [MagicMock(), MagicMock()]

    scalar_result = MagicMock()
    scalar_result.all.return_value = expected

    query_result = MagicMock()
    query_result.scalars.return_value = scalar_result

    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.scalars_all(statement)

    assert result == expected
    session.execute.assert_awaited_once_with(statement)
    query_result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_delegates_to_session(session):
    model = MagicMock()
    identity = 42
    expected = MagicMock()

    session.get.return_value = expected

    db = ClientReadDatabase(session)

    result = await db.get(model, identity)

    assert result is expected
    session.get.assert_awaited_once_with(model, identity)


@pytest.mark.asyncio
async def test_refresh_delegates_to_session(session):
    obj = MagicMock()
    db = ClientReadDatabase(session)

    result = await db.refresh(obj)

    assert result is None
    session.refresh.assert_awaited_once_with(obj)


@pytest.mark.asyncio
async def test_write_commit_delegates_to_session(session):
    db = ClientWriteDatabase(session)

    result = await db.commit()

    assert result is None
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_write_rollback_delegates_to_session(session):
    db = ClientWriteDatabase(session)

    result = await db.rollback()

    assert result is None
    session.rollback.assert_awaited_once_with()


def test_write_add_delegates_to_session(session):
    obj = MagicMock()
    db = ClientWriteDatabase(session)

    result = db.add(obj)

    assert result is None
    session.add.assert_called_once_with(obj)


@pytest.mark.asyncio
async def test_write_delete_delegates_to_session(session):
    obj = MagicMock()
    db = ClientWriteDatabase(session)

    result = await db.delete(obj)

    assert result is None
    session.delete.assert_awaited_once_with(obj)


@pytest.mark.parametrize(
    ("raw_score", "expected"),
    [
        (0, 0.0),
        (10, 10.0),
        (-5, 0.0),
        (15, 10.0),
        (4.24, 4.0),
        (4.25, 4.0),
        (4.26, 4.5),
        (4.74, 4.5),
        (4.75, 5.0),
        ("7.2", 7.0),
    ],
)
def test_normalize_score_clamps_and_rounds(raw_score, expected):
    result = ClientWriteDatabase._normalize_score(raw_score)

    assert result == expected


def test_normalize_score_rejects_none():
    with pytest.raises(BadRequestError) as exc_info:
        ClientWriteDatabase._normalize_score(None)

    error = exc_info.value

    assert error.code == "SCORE_MISSING"
    assert error.message == "Score is required."


@pytest.mark.parametrize(
    "invalid_score",
    [
        "not-a-number",
        object(),
    ],
)
def test_normalize_score_propagates_invalid_numeric_value(invalid_score):
    with pytest.raises((TypeError, ValueError)):
        ClientWriteDatabase._normalize_score(invalid_score)