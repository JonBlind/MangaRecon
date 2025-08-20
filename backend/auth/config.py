import os
from pydantic import BaseSettings
from fastapi_users.authentication import CookieTransport, JWTStrategy, AuthenticationBackend

class Settings(BaseSettings):
    auth_secret: str = os.getenv("AUTH_SECRET") or ""
    debug: bool = (os.getenv("DEBUG","false").lower() == "true")

settings = Settings()

if not settings.auth_secret:
    raise RuntimeError("AUTH_SECRET not found in environment")

cookie_transport = CookieTransport(
    cookie_name="auth",
    cookie_max_age=3600,
    cookie_secure=not settings.debug,
    cookie_samesite="lax",
)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.auth_secret, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
