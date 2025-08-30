from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from backend.db.client_db import ClientDatabase
from backend.db.models.user import User
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.schemas.user import UserRead, UserUpdate, ChangePassword
from backend.auth.user_manager import get_user_manager, UserManager
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])

@router.get("/me", response_model=dict)
@limiter.limit("120/minute")
async def get_my_profile(
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    """
    Return the authenticated user's profile (sanitized).
    """
    try:
        logger.info(f"Fetching profile for user {user.id}")
        result = await db.session.execute(
            select(User).where(User.id == user.id)
        )
        me = result.scalar_one_or_none()

        if not me:
            logger.warning(f"No user row found for {user.id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

        validated = UserRead.model_validate(me)
        return success("Profile retrieved successfully", data=validated)

    except Exception as e:
        logger.error(f"Failed to retrieve profile for user {user.id}: {e}", exc_info=True)
        return error("Failed to retrieve profile", detail=str(e))
    
@router.patch("/me", response_model=dict)
@limiter.limit("10/minute")
async def update_my_profile(
    payload: UserUpdate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    """
    Update the authenticated user's profile.
    Only 'displayname' is allowed to change here.
    """
    try:
        logger.info(f"User {user.id} updating profile")

        result = await db.session.execute(
            select(User).where(User.id == user.id)
        )
        me = result.scalar_one_or_none()

        if not me:
            logger.warning(f"User {user.id} attempted to update a non-existent profile")
            return error("Profile not found", detail="No profile exists for this user.")

        # Reject unsupported fields here (email/password changes handled in the future)
        incoming = payload.model_dump(exclude_unset=True)
        if any(k in incoming for k in ("email", "password")):
            logger.warning(f"User {user.id} attempted to change restricted fields via /profiles/me")
            return error("Not allowed", detail="Use the account settings flow to change email or password.")

        if "displayname" in incoming:
            setattr(me, "displayname", incoming["displayname"])
        else:
            return success("No changes applied", data=UserRead.model_validate(me))

        await db.session.commit()
        await db.session.refresh(me)

        validated = UserRead.model_validate(me)
        return success("Profile updated successfully", data=validated)

    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to update profile for user {user.id}: {e}", exc_info=True)
        return error("Failed to update profile", detail=str(e))
    
@router.post("/me/change-password", response_model=dict)
@limiter.limit("10/minute")
async def change_my_password(
    payload: ChangePassword,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Change the authenticated user's password by verifying the current password.
    Done only if user knows their password, but still desires a change.
    """
    try:
        logger.info(f"User {user.id} attempting password change")

        # Verify current password
        if not user_manager.password_helper.verify(payload.current_password, user.hashed_password):
            logger.warning(f"User {user.id} provided incorrect current password")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

        # validate password
        await user_manager.validate_password(payload.new_password, user)

        # Update hash and persist
        user.hashed_password = user_manager.password_helper.hash(payload.new_password)
        await db.session.commit()
        await db.session.refresh(user)

        validated = UserRead.model_validate(user)
        return success("Password changed successfully", data=validated)

    except HTTPException:
        raise
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Failed to change password for user {user.id}: {e}", exc_info=True)
        return error("Failed to change password", detail=str(e))