'''
Auth and user-management routes assembled from FastAPI Users.

Routes:
- /auth/jwt/*      : Login/logout via JWT cookie transport.
- /auth/register   : Account registration.
- /auth/verify/*   : Email verification flows.
- /auth/reset/*    : Password reset flows.
- /users/*         : User CRUD (admin/self as configured).
'''

from fastapi import APIRouter
from backend.auth.dependencies import fastapi_users
from backend.auth.config import auth_backend
from backend.schemas.user import UserCreate, UserRead, UserUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(UserRead)

# Combine everything into a central Auth router
router = APIRouter()
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])           # JWT auth (login/logout)
router.include_router(register_router, prefix="/auth", tags=["auth"])           # Registration
router.include_router(users_router, prefix="/users", tags=["users"])            # Users (read/update)
router.include_router(reset_password_router, prefix="/auth", tags=["auth"])     # Reset password
router.include_router(verify_router, prefix="/auth", tags=["auth"])             # Email verification