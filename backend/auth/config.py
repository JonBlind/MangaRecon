'''
Authentication configuration and FastAPI Users backend wiring.

- Loads settings from environment (.env via pydantic-settings).
- Configures cookie transport and JWT strategy.
- Exposes `auth_backend` for use with FastAPI Users routers/dependencies.
'''

import os
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi_users.authentication import CookieTransport, JWTStrategy, AuthenticationBackend

class Settings(BaseSettings):
    '''
    Strongly-typed auth settings loaded from environment variables.

    Attributes:
        auth_secret (str): Secret used to sign JWTs and tokens.
        debug (bool): Enables relaxed cookie security when True.

    Notes:
        - `.env` is respected via SettingsConfigDict.
        - Extra env vars are ignored (extra="ignore").
    '''
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore")

    auth_secret: str = Field(..., validation_alias=AliasChoices("AUTH_SECRET"))
    debug: bool = Field(False, validation_alias=AliasChoices("DEBUG"))

settings = Settings()

if not settings.auth_secret:
    raise RuntimeError("AUTH_SECRET not found in environment")

# Cookie transport for auth flows; uses secure flags unless DEBUG=true.
cookie_transport = CookieTransport(
    cookie_name="auth",
    cookie_max_age=3600,
    cookie_secure=not settings.debug,
    cookie_samesite="lax",
)

def get_jwt_strategy() -> JWTStrategy:
    '''
    Build the JWT strategy used by FastAPI Users.

    Returns:
        JWTStrategy: Configured with `settings.auth_secret` and a 1-hour lifetime.
    '''
    return JWTStrategy(secret=settings.auth_secret, lifetime_seconds=3600)

# Authentication backend combining transport and the JWT strategy.
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
