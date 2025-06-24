from fastapi import APIRouter
from backend.auth.dependencies import fastapi_users
from backend.auth.config import auth_backend
from backend.schemas.user import UserCreate, UserRead, UserUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)