import os
from dotenv import load_dotenv
from pydantic import AliasChoices, Field
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

    mangaupdates_base_url: str = ("https://api.mangaupdates.com/v1")
    mangaupdates_timeout_seconds: float = Field(default=10.0, gt=0)
    mangaupdates_min_request_interval_seconds: float = Field(default=1.0, ge=0)
    mangaupdates_user_agent: str = "MangaRecon/0.1"

settings = Settings()

origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]