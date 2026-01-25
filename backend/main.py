'''
FastAPI application entrypoint for MangaRecon.

- Loads settings from environment (via pydantic-settings).
- Registers CORS, exception handlers, and global rate limiter.
- Wires up all routers (auth, collections, manga, ratings, recommendations, profiles, metadata).
- Basic health check at GET /healthz.
'''

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from backend.utils.errors import register_exception_handlers
from backend.utils.rate_limit import register_rate_limiter
from backend.cache.redis import get_redis_cache
from dotenv import load_dotenv
from backend.routes import (
    collection_routes,
    manga_routes,
    rating_routes,
    recommendation_routes,
    profile_routes,
    metadata_routes
)

from backend.auth import router as auth_routes

ENV = os.getenv("MANGARECON_ENV", "dev").lower()
if ENV == "test":
    load_dotenv(".env.test", override=True)
else:
    load_dotenv(".env", override=False)

class Settings(BaseSettings):
    '''
    Application settings (CORS, origins, environment flags, and other toggles)
    loaded via environment variables and used during app construction.
    '''
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore")
    frontend_origins: str = Field(..., validation_alias=AliasChoices("FRONTEND_ORIGINS"))
    debug: bool = False

settings = Settings()
origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]
ENV = os.getenv("MANGARECON_ENV", "dev").lower()

@asynccontextmanager
async def lifespan(app: FastAPI):
    '''
    Application lifespan context.

    Sets up and tears down global resources (e.g., Redis, rate limiter,
    DB connections) at startup/shutdown.

    Yields:
        None: Control is passed to the application while resources are active.
    '''
    redis_cache = None

    if ENV != "test":
        redis_cache = get_redis_cache()

    try:
        yield
    finally:
        if redis_cache is not None:
            await redis_cache.close()

def create_app() -> FastAPI:
    '''
    Primary method responsible for producing the backend client application.
    
    Returns:
        FastAPI
    '''
    app = FastAPI(lifespan=lifespan, debug=settings.debug)

    register_exception_handlers(app)

    # Rate limiting is disabled in tests
    if ENV != "test":
        register_rate_limiter(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    app.include_router(auth_routes.router)
    app.include_router(collection_routes.router)
    app.include_router(manga_routes.router)
    app.include_router(rating_routes.router)
    app.include_router(recommendation_routes.router)
    app.include_router(profile_routes.router)
    app.include_router(metadata_routes.router)

    # health check
    @app.get("/healthz")
    def health():
        '''Simple probe used for uptime check.'''
        return {"message": "MangaRecon API is running."}

    return app

app = create_app()