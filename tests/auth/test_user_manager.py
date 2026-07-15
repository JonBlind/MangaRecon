from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.auth import user_manager
from backend.auth.user_manager import UserManager


@pytest.fixture
def fake_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "original@example.com"
    user.displayname = "Original Name"
    user.is_verified = True

    return user


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
        f"User {fake_user.id} has registred."
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

    await manager.on_after_register(
        fake_user,
        request=request,
    )

    log_info.assert_called_once_with(
        f"User {fake_user.id} has registred."
    )


@pytest.mark.asyncio
async def test_on_after_forgot_password_logs_user_and_token(
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

    result = await manager.on_after_forgot_password(
        fake_user,
        "reset-token",
    )

    assert result is None

    log_info.assert_called_once_with(
        f"User {fake_user.id} requested a password reset. "
        "Token: reset-token"
    )


@pytest.mark.asyncio
async def test_on_after_request_verify_logs_user_and_token(
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

    result = await manager.on_after_request_verify(
        fake_user,
        "verification-token",
    )

    assert result is None

    log_info.assert_called_once_with(
        f"Verification Email Sent for user {fake_user.id}. "
        "Token: verification-token"
    )


@pytest.mark.asyncio
async def test_update_delegates_unchanged_update_to_base_manager(
    monkeypatch,
    manager,
    fake_user,
):
    updated_user = MagicMock()

    base_update = AsyncMock(
        return_value=updated_user,
    )

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )

    update_dict = {
        "username": "new-username",
    }

    result = await manager.update(
        fake_user,
        update_dict,
    )

    assert result is updated_user

    base_update.assert_awaited_once_with(
        fake_user,
        update_dict,
        safe=False,
        request=None,
    )

    assert update_dict == {
        "username": "new-username",
    }


@pytest.mark.asyncio
async def test_update_logs_displayname_change(
    monkeypatch,
    manager,
    fake_user,
):
    updated_user = MagicMock()

    base_update = AsyncMock(
        return_value=updated_user,
    )
    log_info = MagicMock()

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )
    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    update_dict = {
        "displayname": "Updated Name",
    }

    result = await manager.update(
        fake_user,
        update_dict,
    )

    assert result is updated_user

    log_info.assert_called_once_with(
        f"User {fake_user.id} changed their displayname to: "
        "Updated Name"
    )

    base_update.assert_awaited_once_with(
        fake_user,
        update_dict,
        safe=False,
        request=None,
    )


@pytest.mark.asyncio
async def test_update_marks_user_unverified_when_email_changes(
    monkeypatch,
    manager,
    fake_user,
):
    updated_user = MagicMock()

    base_update = AsyncMock(
        return_value=updated_user,
    )
    log_info = MagicMock()

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )
    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    update_dict = {
        "email": "updated@example.com",
    }

    result = await manager.update(
        fake_user,
        update_dict,
    )

    assert result is updated_user
    assert fake_user.is_verified is False

    log_info.assert_called_once_with(
        f"User {fake_user.id} is changing their eail to "
        "updated@example.com"
    )

    base_update.assert_awaited_once_with(
        fake_user,
        update_dict,
        safe=False,
        request=None,
    )


@pytest.mark.asyncio
async def test_update_hashes_password_before_delegating(
    monkeypatch,
    manager,
    fake_user,
):
    updated_user = MagicMock()

    base_update = AsyncMock(
        return_value=updated_user,
    )
    log_info = MagicMock()

    password_helper = MagicMock()
    password_helper.hash.return_value = "secure-hash"

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )
    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    manager.password_helper = password_helper

    update_dict = {
        "password": "plain-password",
    }

    result = await manager.update(
        fake_user,
        update_dict,
    )

    assert result is updated_user

    password_helper.hash.assert_called_once_with(
        "plain-password"
    )

    assert "password" not in update_dict
    assert update_dict["hashed_password"] == "secure-hash"

    log_info.assert_called_once_with(
        f"User {fake_user.id} updated their password."
    )

    base_update.assert_awaited_once_with(
        fake_user,
        {
            "hashed_password": "secure-hash",
        },
        safe=False,
        request=None,
    )


@pytest.mark.asyncio
async def test_update_handles_displayname_email_and_password_together(
    monkeypatch,
    manager,
    fake_user,
):
    updated_user = MagicMock()

    base_update = AsyncMock(
        return_value=updated_user,
    )
    log_info = MagicMock()

    password_helper = MagicMock()
    password_helper.hash.return_value = "secure-hash"

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )
    monkeypatch.setattr(
        user_manager.logger,
        "info",
        log_info,
    )

    manager.password_helper = password_helper

    request = MagicMock()

    update_dict = {
        "displayname": "Updated Name",
        "email": "updated@example.com",
        "password": "plain-password",
    }

    result = await manager.update(
        fake_user,
        update_dict,
        safe=True,
        request=request,
    )

    assert result is updated_user
    assert fake_user.is_verified is False

    password_helper.hash.assert_called_once_with(
        "plain-password"
    )

    assert update_dict == {
        "displayname": "Updated Name",
        "email": "updated@example.com",
        "hashed_password": "secure-hash",
    }

    assert log_info.call_args_list == [
        (
            (
                f"User {fake_user.id} changed their displayname to: "
                "Updated Name",
            ),
            {},
        ),
        (
            (
                f"User {fake_user.id} is changing their eail to "
                "updated@example.com",
            ),
            {},
        ),
        (
            (
                f"User {fake_user.id} updated their password.",
            ),
            {},
        ),
    ]

    base_update.assert_awaited_once_with(
        fake_user,
        update_dict,
        safe=True,
        request=request,
    )


@pytest.mark.asyncio
async def test_update_propagates_base_manager_error(
    monkeypatch,
    manager,
    fake_user,
):
    base_update = AsyncMock(
        side_effect=RuntimeError("update failed"),
    )

    monkeypatch.setattr(
        user_manager.BaseUserManager,
        "update",
        base_update,
    )

    with pytest.raises(
        RuntimeError,
        match="update failed",
    ):
        await manager.update(
            fake_user,
            {
                "displayname": "Updated Name",
            },
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