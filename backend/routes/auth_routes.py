'''
Auth and user-management routes assembled from FastAPI Users.

Routes:
- /auth/jwt/*      : Login/logout via JWT cookie transport.
- /auth/register   : Account registration.
- /auth/verify/*   : Email verification flows.
- /auth/reset/*    : Password reset flows.
'''

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import exceptions
from backend.auth.dependencies import fastapi_users
from backend.auth.config import auth_backend
from backend.auth.user_manager import UserManager, get_user_manager
from backend.schemas.user import UserCreate, UserRead

auth_router = fastapi_users.get_auth_router(auth_backend, requires_verification=True)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(UserRead)

# Combine everything into a central Auth router
router = APIRouter()
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])           # JWT auth (login/logout)
router.include_router(register_router, prefix="/auth", tags=["auth"])           # Registration
router.include_router(reset_password_router, prefix="/auth", tags=["auth"])     # Reset password
router.include_router(verify_router, prefix="/auth", tags=["auth"])             # Email verification


@router.get("/auth/reset-password", status_code=status.HTTP_204_NO_CONTENT, tags=["auth"])
async def validate_password_reset_token(
    token: str,
    user_manager: UserManager = Depends(get_user_manager),
):
    """Validate a reset link without consuming its one-time token."""
    try:
        await user_manager.validate_reset_password_token(token)
    except (
        exceptions.InvalidResetPasswordToken,
        exceptions.UserNotExists,
        exceptions.UserInactive,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RESET_PASSWORD_BAD_TOKEN",
        ) from exc
