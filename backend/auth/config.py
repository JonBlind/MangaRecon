import os
from typing import Literal

from pydantic import AliasChoices, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi_users.authentication import CookieTransport, JWTStrategy, AuthenticationBackend

_ENV = os.getenv("MANGARECON_ENV", "prod").lower().strip()


def _default_email_delivery_mode() -> str:
    if _ENV == "test":
        return "disabled"
    if _ENV == "dev":
        return "console"
    return "smtp"


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
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore")

    auth_secret: str | None = Field(None, validation_alias=AliasChoices("AUTH_SECRET"))
    debug: bool = Field(False, validation_alias=AliasChoices("DEBUG"))
    frontend_url: str | None = Field(
        None,
        validation_alias=AliasChoices("FRONTEND_URL"),
    )
    email_delivery_mode: Literal["console", "smtp", "disabled"] = Field(
        default_factory=_default_email_delivery_mode,
        validation_alias=AliasChoices("EMAIL_DELIVERY_MODE"),
    )
    smtp_host: str | None = Field(
        None,
        validation_alias=AliasChoices("SMTP_HOST"),
    )
    smtp_port: int = Field(
        587,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("SMTP_PORT"),
    )
    smtp_username: str | None = Field(
        None,
        validation_alias=AliasChoices("SMTP_USERNAME"),
    )
    smtp_password: str | None = Field(
        None,
        validation_alias=AliasChoices("SMTP_PASSWORD"),
    )
    smtp_from_email: EmailStr | None = Field(
        None,
        validation_alias=AliasChoices("SMTP_FROM_EMAIL"),
    )
    smtp_from_name: str = Field(
        "MangaRecon",
        validation_alias=AliasChoices("SMTP_FROM_NAME"),
    )
    smtp_starttls: bool = Field(
        True,
        validation_alias=AliasChoices("SMTP_STARTTLS"),
    )
    smtp_use_ssl: bool = Field(
        False,
        validation_alias=AliasChoices("SMTP_USE_SSL"),
    )
    smtp_timeout_seconds: float = Field(
        10.0,
        gt=0,
        validation_alias=AliasChoices("SMTP_TIMEOUT_SECONDS"),
    )

settings = Settings()
if not settings.auth_secret:
    if _ENV == "test":
        settings.auth_secret = "some-fake-secret-for-tests-NOT-4-USE"
    else:
        raise RuntimeError("AUTH_SECRET is required (set AUTH_SECRET or run with MANGARECON_ENV=test).")


def validate_email_config() -> None:
    """Validate settings needed to produce and deliver verification links."""
    if _ENV == "prod" and settings.email_delivery_mode != "smtp":
        raise RuntimeError(
            "MANGARECON_ENV=prod requires EMAIL_DELIVERY_MODE=smtp."
        )

    if settings.email_delivery_mode == "disabled":
        return

    if not settings.frontend_url:
        raise RuntimeError(
            "FRONTEND_URL is required when email verification delivery is enabled."
        )

    if settings.email_delivery_mode != "smtp":
        return

    missing = [
        name
        for name, value in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_FROM_EMAIL", settings.smtp_from_email),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "EMAIL_DELIVERY_MODE=smtp requires: "
            + ", ".join(missing)
            + "."
        )

    if bool(settings.smtp_username) != bool(settings.smtp_password):
        raise RuntimeError(
            "SMTP_USERNAME and SMTP_PASSWORD must either both be set or both be omitted."
        )

    if settings.smtp_starttls and settings.smtp_use_ssl:
        raise RuntimeError(
            "SMTP_STARTTLS and SMTP_USE_SSL cannot both be true."
        )

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
