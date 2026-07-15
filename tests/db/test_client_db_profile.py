from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.db import client_db
from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)


@pytest.fixture
def session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_get_profile_by_email_returns_user(session):
    user = MagicMock()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = user
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_profile_by_email(
        "reader@example.com"
    )

    assert result is user
    session.execute.assert_awaited_once()

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert '"user".email' in sql
    assert "reader@example.com" in compiled.params.values()


@pytest.mark.asyncio
async def test_get_profile_by_email_returns_none_when_missing(
    session,
):
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_profile_by_email(
        "missing@example.com"
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_profile_by_email_logs_and_reraises_sqlalchemy_error(
    monkeypatch,
    session,
):
    error = SQLAlchemyError("database unavailable")
    session.execute.side_effect = error

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientReadDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="database unavailable",
    ):
        await db.get_profile_by_email(
            "reader@example.com"
        )

    log_error.assert_called_once()
    message = log_error.call_args.args[0]

    assert "Failed to fetch user by email" in message
    assert "reader@example.com" in message
    assert log_error.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_get_profile_by_identifier_returns_user_by_query(
    session,
):
    user = MagicMock()

    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = user
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_profile_by_identifier(
        "reader"
    )

    assert result is user

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    sql = str(statement)

    assert '"user".username' in sql
    assert '"user".email' in sql
    assert " OR " in sql
    assert "reader" in compiled.params.values()


@pytest.mark.asyncio
async def test_get_profile_by_identifier_returns_none_when_missing(
    session,
):
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    session.execute.return_value = query_result

    db = ClientReadDatabase(session)

    result = await db.get_profile_by_identifier(
        "missing-user"
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_profile_by_identifier_logs_and_reraises_error(
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
        await db.get_profile_by_identifier(
            "reader"
        )

    log_error.assert_called_once()
    message = log_error.call_args.args[0]

    assert "Failed to fetch user by identifier reader" in message
    assert log_error.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_create_profile_adds_commits_refreshes_and_returns_user(
    monkeypatch,
    session,
):
    profile = MagicMock()

    user_constructor = MagicMock(
        return_value=profile
    )
    monkeypatch.setattr(
        client_db,
        "User",
        user_constructor,
    )

    db = ClientWriteDatabase(session)

    data = {
        "email": "reader@example.com",
        "username": "reader",
        "hashed_password": "hash",
    }

    result = await db.create_profile(data)

    assert result is profile

    user_constructor.assert_called_once_with(**data)
    session.add.assert_called_once_with(profile)
    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(profile)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_profile_rolls_back_and_reraises_commit_error(
    monkeypatch,
    session,
):
    profile = MagicMock()

    monkeypatch.setattr(
        client_db,
        "User",
        MagicMock(return_value=profile),
    )

    session.commit.side_effect = SQLAlchemyError(
        "commit failed"
    )

    log_error = MagicMock()
    monkeypatch.setattr(
        client_db.logger,
        "error",
        log_error,
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="commit failed",
    ):
        await db.create_profile(
            {
                "email": "reader@example.com",
            }
        )

    session.add.assert_called_once_with(profile)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()
    session.refresh.assert_not_awaited()

    log_error.assert_called_once()
    assert "Error creating profile" in log_error.call_args.args[0]
    assert log_error.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_create_profile_rolls_back_when_refresh_fails(
    monkeypatch,
    session,
):
    profile = MagicMock()

    monkeypatch.setattr(
        client_db,
        "User",
        MagicMock(return_value=profile),
    )

    session.refresh.side_effect = SQLAlchemyError(
        "refresh failed"
    )

    db = ClientWriteDatabase(session)

    with pytest.raises(
        SQLAlchemyError,
        match="refresh failed",
    ):
        await db.create_profile(
            {
                "email": "reader@example.com",
            }
        )

    session.commit.assert_awaited_once_with()
    session.refresh.assert_awaited_once_with(profile)
    session.rollback.assert_awaited_once_with()