from __future__ import annotations

from pwdlib.exceptions import UnknownHashError

from backend.auth.user_manager import UserManager
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.repositories.profile_repo import fetch_user_by_id
from backend.schemas.user import UserRead, UserUpdate, ChangePassword
from backend.utils.domain_exceptions import BadRequestError, NotFoundError, ForbiddenError

async def get_my_profile(*, user_id, user_db: ClientReadDatabase) -> UserRead:
    """
    Return the authenticated user's profile.
    """
    me = await fetch_user_by_id(user_db, user_id=user_id)
    if not me:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    return UserRead.model_validate(me)


async def update_my_profile(*, user_id, payload: UserUpdate, user_db: ClientWriteDatabase) -> UserRead | None:
    """
    Update the authenticated user's profile fields.
    Only displayname is supported here.
    Returns:
        UserRead if updated, None if no changes applied.
    """
    me = await fetch_user_by_id(user_db, user_id=user_id)
    if not me:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found.")

    incoming = payload.model_dump(exclude_unset=True)

    # Reject unsupported fields (email/password changes handled in the future)
    if any(k in incoming for k in ("email", "password")):
        raise ForbiddenError(code="PROFILE_FIELD_FORBIDDEN", message="Not allowed.")

    if "displayname" not in incoming:
        return None

    setattr(me, "displayname", incoming["displayname"])

    await user_db.commit()
    await user_db.refresh(me)

    return UserRead.model_validate(me)


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
    try:
        verified, _updated_hash = user_manager.password_helper.verify_and_update(
            payload.current_password,
            user.hashed_password,
        )
    except UnknownHashError:
        raise BadRequestError(code="CURRENT_PASSWORD_INCORRECT", message="Current password is incorrect.")

    if not verified:
        raise BadRequestError(code="CURRENT_PASSWORD_INCORRECT", message="Current password is incorrect.")

    user.hashed_password = user_manager.password_helper.hash(payload.new_password)

    await user_db.commit()
    await user_db.refresh(user)

    return UserRead.model_validate(user)
