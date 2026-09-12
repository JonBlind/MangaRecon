from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from pwdlib.exceptions import UnknownHashError
from sqlalchemy.exc import IntegrityError

from backend.auth.user_manager import UserManager
from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)
from backend.repositories.profile_repo import (
    delete_user_row,
    fetch_user_by_id,
    fetch_user_for_deletion,
    get_owned_collection_ids,
)
from backend.schemas.user import (
    ChangePassword,
    DeleteAccount,
    ProfileUpdate,
    UserRead,
)
from backend.utils.domain_exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)


USERNAME_CHANGE_COOLDOWN = timedelta(days=30)
logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.

    Kept as a separate function so tests can replace it with a
    predictable timestamp.
    """
    return datetime.now(timezone.utc)


async def get_my_profile(
    *,
    user_id,
    user_db: ClientReadDatabase,
) -> UserRead:
    """
    Return the authenticated user's profile.
    """
    user = await fetch_user_by_id(
        user_db,
        user_id=user_id,
    )

    if user is None:
        raise NotFoundError(
            code="PROFILE_NOT_FOUND",
            message="Profile not found.",
        )

    return UserRead.model_validate(user)


async def update_my_profile(
    *,
    user_id,
    payload: ProfileUpdate,
    user_db: ClientWriteDatabase,
) -> UserRead | None:
    """
    Update the authenticated user's editable profile fields.

    Username changes are limited to once every 30 days.

    Returns:
        UserRead if at least one field was updated.
        None if no effective changes were supplied.
    """
    user = await fetch_user_by_id(user_db, user_id=user_id)

    if user is None:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    requested_updates = payload.model_dump(
        exclude_unset=True,
    )
    age_confirmed = requested_updates.pop(
        "confirm_adult_content_age",
        False,
    )

    if (
        requested_updates.get("show_adult_content") is True
        and getattr(user, "show_adult_content", False) is False
        and age_confirmed is not True
    ):
        raise BadRequestError(
            code="ADULT_CONTENT_AGE_CONFIRMATION_REQUIRED",
            message=(
                "Confirm that you are at least 18 years old "
                "before enabling adult content."
            ),
        )

    # Keep only values that differ from the stored profile.
    effective_updates = {
        field: value
        for field, value in requested_updates.items()
        if getattr(user, field) != value
    }

    if not effective_updates:
        return None

    username_is_changing = ("username" in effective_updates)

    now = utc_now()

    if (username_is_changing and user.username_changed_at is not None):
        next_change_at = (user.username_changed_at + USERNAME_CHANGE_COOLDOWN)

        if now < next_change_at:
            raise ConflictError(
                code="USERNAME_CHANGE_COOLDOWN",
                message=(
                    "Username can only be changed once "
                    "every 30 days."
                ),
                detail={
                    "next_change_at": (
                        next_change_at.isoformat()
                    ),
                },
            )

    for field, value in effective_updates.items():
        setattr(user, field, value)

    if username_is_changing:
        user.username_changed_at = now

    try:
        await user_db.commit()

    except IntegrityError as exc:
        await user_db.rollback()

        if username_is_changing:
            raise ConflictError(code="USERNAME_TAKEN", message=("That username is already in use.")) from exc
        raise

    await user_db.refresh(user)

    return UserRead.model_validate(user)


async def change_my_password(
    *,
    user,
    payload: ChangePassword,
    user_db: ClientWriteDatabase,
    user_manager: UserManager,
) -> UserRead:
    """
    Change the authenticated user's password after
    verifying the current password.
    """
    db_user = await fetch_user_by_id(
        user_db,
        user_id=user.id,
    )

    if db_user is None:
        raise NotFoundError(
            code="PROFILE_NOT_FOUND",
            message="Profile not found.",
        )

    try:
        verified, _updated_hash = (
            user_manager.password_helper.verify_and_update(
                payload.current_password,
                db_user.hashed_password,
            )
        )

    except UnknownHashError as exc:
        raise BadRequestError(
            code="CURRENT_PASSWORD_INCORRECT",
            message="Current password is incorrect.",
        ) from exc

    if not verified:
        raise BadRequestError(
            code="CURRENT_PASSWORD_INCORRECT",
            message="Current password is incorrect.",
        )

    db_user.hashed_password = (
        user_manager.password_helper.hash(
            payload.new_password,
        )
    )

    await user_db.commit()
    await user_db.refresh(db_user)

    return UserRead.model_validate(db_user)


async def delete_my_account(
    *,
    user_id,
    payload: DeleteAccount,
    user_db: ClientWriteDatabase,
    user_manager: UserManager,
    redis_cache,
) -> None:
    """Delete account-owned rows atomically, then clear recommendation cache."""
    account = await fetch_user_for_deletion(user_db, user_id=user_id)
    if account is None:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    try:
        valid_password, _ = user_manager.password_helper.verify_and_update(
            payload.current_password,
            account.hashed_password,
        )
    except UnknownHashError:
        valid_password = False

    if not valid_password:
        await user_db.rollback()
        raise BadRequestError(
            code="CURRENT_PASSWORD_INCORRECT",
            message="Current password is incorrect.",
        )

    try:
        collection_ids = await get_owned_collection_ids(user_db, user_id=user_id)
        await delete_user_row(user_db, user_id=user_id)
        await user_db.commit()
    except Exception:
        await user_db.rollback()
        raise

    cache_keys = [
        f"recommendations:{user_id}:{collection_id}:{visibility}"
        for collection_id in collection_ids
        for visibility in ("safe", "adult")
    ]
    if cache_keys:
        try:
            await redis_cache.delete_multiple(*cache_keys)
        except Exception:
            # The database deletion has committed. Production cache entries
            # expire, and deleted users cannot authenticate to retrieve them.
            logger.exception("Failed to clear deleted account recommendation cache.")
