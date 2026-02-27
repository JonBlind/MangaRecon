from fastapi import APIRouter, Depends, Request
from backend.db.client_db import ClientWriteDatabase, ClientReadDatabase
from backend.db.models.user import User
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_user as current_user
from backend.schemas.user import UserRead, UserUpdate, ChangePassword
from backend.auth.user_manager import get_user_manager, UserManager
from backend.utils.response import success
from backend.utils.rate_limit import limiter
from backend.services.profile_service import (
    get_my_profile as svc_get_my_profile,
    update_my_profile as svc_update_my_profile,
    change_my_password as svc_change_my_password,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/me", response_model=dict)
@limiter.limit("120/minute")
async def get_my_profile(
    request: Request,
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
):
    '''
    Return the authenticated user's profile.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        db (ClientDatabase): User-domain database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the user's profile data.
    '''
    try:
        logger.info("Fetching profile for user %s", user.id)
        validated = await svc_get_my_profile(user_id=user.id, user_db=db)
        return success("Profile retrieved successfully", data=validated)

    except Exception as e:
        logger.error("Failed to retrieve profile for user %s: %s", user.id, e, exc_info=True)
        raise


@router.patch("/me", response_model=dict)
@limiter.limit("10/minute")
async def update_my_profile(
    request: Request,
    payload: UserUpdate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    '''
    Update the authenticated user's profile fields.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        payload (UserUpdate): Patch payload for profile updates.
        db (ClientDatabase): User-domain database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the updated profile data.
    '''
    try:
        logger.info("User %s updating profile", user.id)
        validated = await svc_update_my_profile(user_id=user.id, payload=payload, user_db=db)

        if validated is None:
            return success("No changes applied", data=UserRead.model_validate(user))

        return success("Profile updated successfully", data=validated)

    except Exception as e:
        logger.error("Failed to update profile for user %s: %s", user.id, e, exc_info=True)
        raise


@router.post("/me/change-password", response_model=dict)
@limiter.limit("10/minute")
async def change_my_password(
    request: Request,
    payload: ChangePassword,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
    user_manager: UserManager = Depends(get_user_manager),
):
    '''
    Change the authenticated user's password after verifying the current password.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        payload (ChangePassword): Change-password payload (current and new passwords).
        db (ClientDatabase): User-domain database client.
        user (User): Currently authenticated, active, verified user.
        user_manager (UserManager): User manager used for password verification and update.

    Returns:
        dict: Standardized response indicating success or an error detail.
    '''
    try:
        logger.info("User %s attempting password change", user.id)
        validated = await svc_change_my_password(
            user=user,
            payload=payload,
            user_db=db,
            user_manager=user_manager,
        )
        return success("Password changed successfully", data=validated)

    except Exception as e:
        logger.error("Failed password change for user %s: %s", user.id, e, exc_info=True)
        raise