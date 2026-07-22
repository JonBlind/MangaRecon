import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.auth import user_manager
from backend.auth.user_manager import UserManager


@pytest.fixture
def fake_user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="original@example.com",
        displayname="Original Name",
        is_verified=True,
    )


@pytest.fixture
def manager():
    user_db = MagicMock()
    return UserManager(user_db)


@pytest.mark.asyncio
async def test_get_user_db_yields_sqlalchemy_user_database(
    monkeypatch,
):
    session = MagicMock()
    adapter = MagicMock()

    database_constructor = MagicMock(
        return_value=adapter,
    )

    monkeypatch.setattr(
        user_manager,
        "SQLAlchemyUserDatabase",
        database_constructor,
    )

    dependency = user_manager.get_user_db(session)

    result = await anext(dependency)

    assert result is adapter

    database_constructor.assert_called_once_with(
        session,
        user_manager.User,
    )

    with pytest.raises(StopAsyncIteration):
        await anext(dependency)


def test_user_manager_uses_centralized_auth_secret():
    assert (
        UserManager.reset_password_token_secret
        == user_manager.settings.auth_secret
    )

    assert (
        UserManager.verification_token_secret
        == user_manager.settings.auth_secret
    )


def test_user_manager_token_lifetimes():
    assert (
        UserManager.reset_password_token_lifetime_seconds
        == 7200
    )

    assert (
        UserManager.verification_token_lifetime_seconds
        == 259200
    )


@pytest.mark.asyncio
async def test_on_after_register_logs_user_registration(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_register(
        fake_user,
    )

    assert result is None

    log_info.assert_called_once_with(
        "User %s registered.",
        fake_user.id,
    )


@pytest.mark.asyncio
async def test_on_after_register_accepts_request(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()
    request = MagicMock()

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_register(
        fake_user,
        request=request,
    )

    assert result is None

    log_info.assert_called_once_with(
        "User %s registered.",
        fake_user.id,
    )


@pytest.mark.asyncio
async def test_on_after_forgot_password_logs_request_without_token(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()
    token = "sensitive-reset-token"

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_forgot_password(
        fake_user,
        token,
    )

    assert result is None

    log_info.assert_called_once_with(
        "Password reset requested for user %s.",
        fake_user.id,
    )

    assert token not in repr(log_info.call_args)


@pytest.mark.asyncio
async def test_on_after_forgot_password_accepts_request(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()
    request = MagicMock()

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_forgot_password(
        fake_user,
        "sensitive-reset-token",
        request=request,
    )

    assert result is None

    log_info.assert_called_once_with(
        "Password reset requested for user %s.",
        fake_user.id,
    )


@pytest.mark.asyncio
async def test_on_after_request_verify_logs_request_without_token(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()
    token = "sensitive-verification-token"

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_request_verify(
        fake_user,
        token,
    )

    assert result is None

    log_info.assert_called_once_with(
        "Email verification requested for user %s.",
        fake_user.id,
    )

    assert token not in repr(log_info.call_args)


@pytest.mark.asyncio
async def test_on_after_request_verify_accepts_request(
    monkeypatch,
    manager,
    fake_user,
):
    log_info = MagicMock()
    request = MagicMock()

    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    result = await manager.on_after_request_verify(
        fake_user,
        "sensitive-verification-token",
        request=request,
    )

    assert result is None

    log_info.assert_called_once_with(
        "Email verification requested for user %s.",
        fake_user.id,
    )


@pytest.mark.asyncio
async def test_get_user_manager_yields_configured_manager():
    user_db = MagicMock()

    dependency = user_manager.get_user_manager(
        user_db,
    )

    result = await anext(dependency)

    assert isinstance(result, UserManager)
    assert result.user_db is user_db

    with pytest.raises(StopAsyncIteration):
        await anext(dependency)