from fastapi import APIRouter
from fastapi.routing import APIRoute
from backend.utils.rate_limit import limiter
from backend.auth.dependencies import fastapi_users
from backend.auth.config import auth_backend
from backend.schemas.user import UserCreate, UserRead, UserUpdate

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)

# Combine everything into a central Auth router
router = APIRouter()
router.include_router(auth_router, prefix="/auth/jwt", tags=["auth"])
router.include_router(register_router, prefix="/auth", tags=["auth"])
router.include_router(users_router, prefix="/users", tags=["users"])


def _decorate_route(router: APIRouter, path: str, methods, *decorators):
    if isinstance(methods, str):
        methods = [methods]
    for r in router.routes:
        if isinstance(r, APIRoute) and r.path == path and any(m in r.methods for m in methods):
            fn = r.endpoint
            for dec in decorators:
                fn = dec(fn)
            r.endpoint = fn
            r.dependant = None
            r.dependants = None


S_AUTH_HOURLY = "auth-ip-hour"
S_AUTH_DAILY  = "auth-ip-day"

# Login
_decorate_route(
    router, "/auth/jwt/login", "POST",
    limiter.limit("5/minute"),
    limiter.shared_limit("50/hour", scope=S_AUTH_HOURLY),
    limiter.shared_limit("500/day", scope=S_AUTH_DAILY),
)

# Logout
_decorate_route(
    router, "/auth/jwt/logout", "POST",
    limiter.limit("120/minute"),
)
# Registration
_decorate_route(
    router, "/auth/register", "POST",
    limiter.limit("3/minute"),
    limiter.shared_limit("50/hour", scope=S_AUTH_HOURLY),
    limiter.shared_limit("500/day", scope=S_AUTH_DAILY),
)

# Forgot password
_decorate_route(
    router, "/auth/forgot-password", "POST",
    limiter.limit("3/hour"),
    limiter.shared_limit("50/hour", scope=S_AUTH_HOURLY),
    limiter.shared_limit("500/day", scope=S_AUTH_DAILY),
)

# Request verify token
_decorate_route(
    router, "/auth/request-verify-token", "POST",
    limiter.limit("5/hour"),
    limiter.shared_limit("50/hour", scope=S_AUTH_HOURLY),
    limiter.shared_limit("500/day", scope=S_AUTH_DAILY),
)

# Reset password
_decorate_route(
    router, "/auth/reset-password", "POST",
    limiter.limit("5/hour"),
    limiter.shared_limit("50/hour", scope=S_AUTH_HOURLY),
    limiter.shared_limit("500/day", scope=S_AUTH_DAILY),
)