import os
from dotenv import load_dotenv
from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_ENVIRONMENTS = {"dev", "test", "prod"}
ENV = os.getenv("MANGARECON_ENV", "prod").strip().lower()

if ENV not in SUPPORTED_ENVIRONMENTS:
    raise RuntimeError("MANGARECON_ENV must be one of: dev, test, prod.")

if ENV == "test":
    load_dotenv(".env.test", override=True)
else:
    load_dotenv(".env", override=False)


class Settings(BaseSettings):
    """
    Application runtime settings loaded from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    frontend_origins: str = Field(..., validation_alias=AliasChoices("FRONTEND_ORIGINS"))
    debug: bool = False
    origin_verify_header_name: SecretStr | None = None
    origin_verify_secret_digest: SecretStr | None = None
    trusted_client_address_header_name: SecretStr | None = None

    # Redis connection limits.
    redis_connect_timeout_seconds: float = Field(default=3.0, gt=0)
    redis_operation_timeout_seconds: float = Field(default=3.0, gt=0)
    redis_ready_timeout_seconds: float = Field(default=5.0, gt=0)
    redis_max_connections: int = Field(default=4, ge=1)

    # Account email and token abuse limits.
    account_email_ip_15_minute_limit: int = Field(default=5, ge=1)
    account_email_ip_daily_limit: int = Field(default=20, ge=1)
    account_email_recipient_cooldown_seconds: int = Field(default=60, ge=1)
    account_email_recipient_hourly_limit: int = Field(default=3, ge=1)
    account_email_recipient_daily_limit: int = Field(default=5, ge=1)
    account_token_ip_minute_limit: int = Field(default=10, ge=1)

    mangaupdates_base_url: str = ("https://api.mangaupdates.com/v1")
    mangaupdates_timeout_seconds: float = Field(default=10.0, gt=0)
    mangaupdates_min_request_interval_seconds: float = Field(default=1.0, ge=0)
    mangaupdates_user_agent: str = "MangaRecon/0.1"

settings = Settings()

if ENV == "prod" and settings.debug:
    raise RuntimeError("MANGARECON_ENV=prod requires DEBUG=false.")

origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]
