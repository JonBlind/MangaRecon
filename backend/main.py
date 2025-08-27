import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings, Field
from backend.utils.errors import register_exception_handlers
from backend.utils.rate_limit import register_rate_limiter

from backend.routes import (
    collection_routes,
    manga_routes,
    rating_routes,
    recommendation_routes,
)

from backend.auth import router as auth_routes

from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    frontend_origins: str = Field(..., env="FRONTEND_ORIGINS")
    debug: bool = Field(False, env="DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
origins = [origin.strip() for origin in settings.frontend_origins.split(",") if origin.strip()]

app = FastAPI(debug=settings.debug)
register_exception_handlers(app)
register_rate_limiter(app)

# Allow frontend dev to interact with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_routes.router)
app.include_router(collection_routes.router)
app.include_router(manga_routes.router)
app.include_router(rating_routes.router)
app.include_router(recommendation_routes.router)

# health check
@app.get("/healthz")
def health():
    return {"message": "MangaRecon API is running."}
