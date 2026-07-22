from __future__ import annotations

from pwdlib.exceptions import UnknownHashError

from backend.auth.user_manager import UserManager
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.repositories.profile_repo import fetch_user_by_id
from backend.schemas.user import UserRead, ProfileUpdate, ChangePassword
from backend.utils.domain_exceptions import BadRequestError, NotFoundError, ForbiddenError

async def get_my_profile(*, user_id, user_db: ClientReadDatabase) -> UserRead:
    """
    Return the authenticated user's profile.
    """
    me = await fetch_user_by_id(user_db, user_id=user_id)
    if not me:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    return UserRead.model_validate(me)


async def update_my_profile(
    *,
    user_id,
    payload: ProfileUpdate,
    user_db: ClientWriteDatabase,
) -> UserRead | None:
    """
    Update the authenticated user's editable profile fields.

    Returns:
        UserRead if at least one field was updated.
        None if no supported changes were supplied.
    """
    user = await fetch_user_by_id(user_db, user_id=user_id)

    if user is None:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    updates = payload.model_dump(exclude_unset=True)

    changed = False

    for field, value in updates.items():
        if getattr(user, field) == value:
            continue

        setattr(user, field, value)
        changed = True

    if not changed:
        return None

    await user_db.commit()
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
    Change the authenticated user's password after verifying the current password.
    """
    db_user = await fetch_user_by_id(
        user_db,
        user_id=user.id,
    )

    if not db_user:
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
    except UnknownHashError:
        raise BadRequestError(
            code="CURRENT_PASSWORD_INCORRECT",
            message="Current password is incorrect.",
        )

    if not verified:
        raise BadRequestError(
            code="CURRENT_PASSWORD_INCORRECT",
            message="Current password is incorrect.",
        )

    db_user.hashed_password = user_manager.password_helper.hash(
        payload.new_password
    )

    await user_db.commit()
    await user_db.refresh(db_user)

    return UserRead.model_validate(db_user)
