import os
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi_users.authentication import CookieTransport, JWTStrategy, AuthenticationBackend

class Settings(BaseSettings):
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
