import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings

from backend.routes import (
    collection_routes,
    manga_routes,
    rating_routes,
    recommendation_routes,
)

from backend.auth import router as auth_routes

app = FastAPI()


class Settings(BaseSettings):
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "*")
    debug: bool = (os.getenv("DEBUG","false").lower() == "true")

settings = Settings()
origins = [settings.frontend_origin] if settings.frontend_origin != "*" else ["*"]


# Allow frontend dev to interact with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
@app.get("/")
def read_root():
    return {"message": "MangaRecon API is running."}