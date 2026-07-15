from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from pwdlib.exceptions import UnknownHashError

from backend.db.models.user import User
from backend.schemas.user import ChangePassword, UserUpdate
from backend.services import profile_service
from backend.utils.domain_exceptions import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
)


def make_user(
    *,
    user_id=None,
    email="user@example.com",
    username="testuser",
    displayname="Test User",
    hashed_password="old-hash",
):
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        username=username,
        displayname=displayname,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
        is_verified=False,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_login=None,
    )


def make_write_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_my_profile_returns_validated_user(monkeypatch):
    user = make_user()

    fetch_user = AsyncMock(return_value=user)
    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        fetch_user,
    )

    db = MagicMock()

    result = await profile_service.get_my_profile(
        user_id=user.id,
        user_db=db,
    )

    assert result.id == user.id
    assert result.email == "user@example.com"
    assert result.username == "testuser"
    assert result.displayname == "Test User"

    fetch_user.assert_awaited_once_with(
        db,
        user_id=user.id,
    )


@pytest.mark.asyncio
async def test_get_my_profile_raises_when_profile_missing(monkeypatch):
    fetch_user = AsyncMock(return_value=None)
    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        fetch_user,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await profile_service.get_my_profile(
            user_id=uuid.uuid4(),
            user_db=MagicMock(),
        )

    error = exc_info.value

    assert error.status_code == 404
    assert error.code == "PROFILE_NOT_FOUND"
    assert error.message == "Profile not found."


@pytest.mark.asyncio
async def test_update_my_profile_updates_displayname(monkeypatch):
    user = make_user(displayname="Old Name")
    db = make_write_db()

    fetch_user = AsyncMock(return_value=user)
    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        fetch_user,
    )

    result = await profile_service.update_my_profile(
        user_id=user.id,
        payload=UserUpdate(displayname="Updated Name"),
        user_db=db,
    )

    assert user.displayname == "Updated Name"
    assert result is not None
    assert result.displayname == "Updated Name"

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_update_my_profile_raises_when_profile_missing(
    monkeypatch,
):
    fetch_user = AsyncMock(return_value=None)
    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        fetch_user,
    )

    db = make_write_db()

    with pytest.raises(NotFoundError) as exc_info:
        await profile_service.update_my_profile(
            user_id=uuid.uuid4(),
            payload=UserUpdate(displayname="Updated Name"),
            user_db=db,
        )

    assert exc_info.value.code == "PROFILE_NOT_FOUND"
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_my_profile_rejects_email_change(monkeypatch):
    user = make_user()
    db = make_write_db()

    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        AsyncMock(return_value=user),
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await profile_service.update_my_profile(
            user_id=user.id,
            payload=UserUpdate(email="new@example.com"),
            user_db=db,
        )

    error = exc_info.value

    assert error.status_code == 403
    assert error.code == "PROFILE_FIELD_FORBIDDEN"
    assert error.message == "Not allowed."

    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_my_profile_rejects_password_change(monkeypatch):
    user = make_user()
    db = make_write_db()

    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        AsyncMock(return_value=user),
    )

    with pytest.raises(ForbiddenError) as exc_info:
        await profile_service.update_my_profile(
            user_id=user.id,
            payload=UserUpdate(password="new-password"),
            user_db=db,
        )

    assert exc_info.value.code == "PROFILE_FIELD_FORBIDDEN"
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_my_profile_returns_none_without_displayname(
    monkeypatch,
):
    user = make_user()
    db = make_write_db()

    monkeypatch.setattr(
        profile_service,
        "fetch_user_by_id",
        AsyncMock(return_value=user),
    )

    result = await profile_service.update_my_profile(
        user_id=user.id,
        payload=UserUpdate(username="newusername"),
        user_db=db,
    )

    assert result is None
    assert user.username == "testuser"

    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_password_updates_hash_and_commits():
    user = make_user(hashed_password="old-hash")
    db = make_write_db()

    password_helper = MagicMock()
    password_helper.verify_and_update.return_value = (
        True,
        None,
    )
    password_helper.hash.return_value = "new-hash"

    user_manager = MagicMock()
    user_manager.password_helper = password_helper

    payload = ChangePassword(
        current_password="old-password",
        new_password="new-password",
    )

    result = await profile_service.change_my_password(
        user=user,
        payload=payload,
        user_db=db,
        user_manager=user_manager,
    )

    password_helper.verify_and_update.assert_called_once_with(
        "old-password",
        "old-hash",
    )
    password_helper.hash.assert_called_once_with("new-password")

    assert user.hashed_password == "new-hash"
    assert result.id == user.id

    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(user)


@pytest.mark.asyncio
async def test_change_password_rejects_unverified_password():
    user = make_user()
    db = make_write_db()

    password_helper = MagicMock()
    password_helper.verify_and_update.return_value = (
        False,
        None,
    )

    user_manager = MagicMock()
    user_manager.password_helper = password_helper

    with pytest.raises(BadRequestError) as exc_info:
        await profile_service.change_my_password(
            user=user,
            payload=ChangePassword(
                current_password="wrong-password",
                new_password="new-password",
            ),
            user_db=db,
            user_manager=user_manager,
        )

    error = exc_info.value

    assert error.status_code == 400
    assert error.code == "CURRENT_PASSWORD_INCORRECT"
    assert error.message == "Current password is incorrect."

    password_helper.hash.assert_not_called()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_change_password_converts_unknown_hash_error():
    user = make_user()
    db = make_write_db()

    password_helper = MagicMock()
    password_helper.verify_and_update.side_effect = UnknownHashError(user.hashed_password)

    user_manager = MagicMock()
    user_manager.password_helper = password_helper

    with pytest.raises(BadRequestError) as exc_info:
        await profile_service.change_my_password(
            user=user,
            payload=ChangePassword(
                current_password="old-password",
                new_password="new-password",
            ),
            user_db=db,
            user_manager=user_manager,
        )

    error = exc_info.value

    assert error.status_code == 400
    assert error.code == "CURRENT_PASSWORD_INCORRECT"
    assert error.message == "Current password is incorrect."

    password_helper.hash.assert_not_called()
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()