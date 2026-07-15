import inspect
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.routes import profile_routes
from backend.schemas.user import (
    ChangePassword,
    UserUpdate,
)
from backend.utils.domain_exceptions import (
    BadRequestError,
)


def handler(function):
    return inspect.unwrap(function)


@pytest.fixture
def user():
    return SimpleNamespace(
        id=uuid.uuid4(),
        email="reader@example.com",
        username="reader",
        displayname="Reader",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        created_at=datetime.now(timezone.utc),
        last_login=None,
    )


@pytest.mark.asyncio
async def test_get_my_profile_forwards_user_id(
    monkeypatch,
    user,
):
    db = MagicMock()
    validated = {
        "id": str(user.id),
        "email": user.email,
    }

    service = AsyncMock(return_value=validated)
    monkeypatch.setattr(
        profile_routes,
        "svc_get_my_profile",
        service,
    )

    result = await handler(
        profile_routes.get_my_profile
    )(
        request=MagicMock(),
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        user_db=db,
    )

    assert result["data"] == validated
    assert result["message"] == (
        "Profile retrieved successfully"
    )


@pytest.mark.asyncio
async def test_update_my_profile_returns_updated_profile(
    monkeypatch,
    user,
):
    db = MagicMock()
    payload = UserUpdate(
        displayname="Updated Reader",
    )

    validated = {
        "id": str(user.id),
        "displayname": "Updated Reader",
    }

    service = AsyncMock(return_value=validated)
    monkeypatch.setattr(
        profile_routes,
        "svc_update_my_profile",
        service,
    )

    result = await handler(
        profile_routes.update_my_profile
    )(
        request=MagicMock(),
        payload=payload,
        db=db,
        user=user,
    )

    service.assert_awaited_once_with(
        user_id=user.id,
        payload=payload,
        user_db=db,
    )

    assert result["data"] == validated
    assert result["message"] == (
        "Profile updated successfully"
    )


@pytest.mark.asyncio
async def test_update_my_profile_returns_current_user_when_no_changes(
    monkeypatch,
    user,
):
    db = MagicMock()
    payload = UserUpdate()

    monkeypatch.setattr(
        profile_routes,
        "svc_update_my_profile",
        AsyncMock(return_value=None),
    )

    result = await handler(
        profile_routes.update_my_profile
    )(
        request=MagicMock(),
        payload=payload,
        db=db,
        user=user,
    )

    assert result["message"] == "No changes applied"

    returned_user = result["data"]
    assert returned_user.id == user.id
    assert returned_user.email == user.email
    assert returned_user.username == user.username
    assert returned_user.displayname == user.displayname


@pytest.mark.asyncio
async def test_change_password_forwards_dependencies(
    monkeypatch,
    user,
):
    db = MagicMock()
    user_manager = MagicMock()

    payload = ChangePassword(
        current_password="old-password",
        new_password="new-password",
    )

    output = {"changed": True}

    service = AsyncMock(return_value=output)
    monkeypatch.setattr(
        profile_routes,
        "svc_change_my_password",
        service,
    )

    result = await handler(
        profile_routes.change_my_password
    )(
        request=MagicMock(),
        payload=payload,
        db=db,
        user=user,
        user_manager=user_manager,
    )

    service.assert_awaited_once_with(
        user=user,
        payload=payload,
        user_db=db,
        user_manager=user_manager,
    )

    assert result["data"] == output
    assert result["message"] == (
        "Password changed successfully"
    )


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "kwargs_factory",
    ),
    [
        (
            "get_my_profile",
            "svc_get_my_profile",
            lambda user: {
                "request": MagicMock(),
                "db": MagicMock(),
                "user": user,
            },
        ),
        (
            "update_my_profile",
            "svc_update_my_profile",
            lambda user: {
                "request": MagicMock(),
                "payload": UserUpdate(
                    displayname="Updated"
                ),
                "db": MagicMock(),
                "user": user,
            },
        ),
        (
            "change_my_password",
            "svc_change_my_password",
            lambda user: {
                "request": MagicMock(),
                "payload": ChangePassword(
                    current_password="old-password",
                    new_password="new-password",
                ),
                "db": MagicMock(),
                "user": user,
                "user_manager": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_profile_routes_reraise_domain_errors(
    monkeypatch,
    user,
    route_name,
    service_name,
    kwargs_factory,
):
    domain_error = BadRequestError(
        code="PROFILE_ERROR",
        message="Profile operation failed.",
    )

    monkeypatch.setattr(
        profile_routes,
        service_name,
        AsyncMock(side_effect=domain_error),
    )

    with pytest.raises(BadRequestError) as exc_info:
        await handler(
            getattr(profile_routes, route_name)
        )(**kwargs_factory(user))

    assert exc_info.value is domain_error


@pytest.mark.parametrize(
    (
        "route_name",
        "service_name",
        "kwargs_factory",
    ),
    [
        (
            "get_my_profile",
            "svc_get_my_profile",
            lambda user: {
                "request": MagicMock(),
                "db": MagicMock(),
                "user": user,
            },
        ),
        (
            "update_my_profile",
            "svc_update_my_profile",
            lambda user: {
                "request": MagicMock(),
                "payload": UserUpdate(
                    displayname="Updated"
                ),
                "db": MagicMock(),
                "user": user,
            },
        ),
        (
            "change_my_password",
            "svc_change_my_password",
            lambda user: {
                "request": MagicMock(),
                "payload": ChangePassword(
                    current_password="old-password",
                    new_password="new-password",
                ),
                "db": MagicMock(),
                "user": user,
                "user_manager": MagicMock(),
            },
        ),
    ],
)
@pytest.mark.asyncio
async def test_profile_routes_log_and_reraise_unexpected_errors(
    monkeypatch,
    user,
    route_name,
    service_name,
    kwargs_factory,
):
    log_error = MagicMock()

    monkeypatch.setattr(
        profile_routes,
        service_name,
        AsyncMock(
            side_effect=RuntimeError(
                "profile service failed"
            )
        ),
    )
    monkeypatch.setattr(
        profile_routes.logger,
        "error",
        log_error,
    )

    with pytest.raises(
        RuntimeError,
        match="profile service failed",
    ):
        await handler(
            getattr(profile_routes, route_name)
        )(**kwargs_factory(user))

    log_error.assert_called_once()
    assert (
        log_error.call_args.kwargs["exc_info"]
        is True
    )