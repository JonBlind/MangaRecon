from typing import AsyncGenerator
import os
from pydantic import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.client_db import ClientDatabase

class Settings(BaseSettings):
    user_write: str | None = os.getenv("UserWriterDB")
    user_read: str | None = os.getenv("UserReaderDB")
    manga_write: str | None = os.getenv("MangaWriterDB")
    manga_read: str | None = os.getenv("MangaReaderDB")

settings = Settings()

# Build engines once
_engine_user_write = create_async_engine(settings.user_write, pool_pre_ping=True) if settings.user_write else None
_engine_user_read = create_async_engine(settings.user_read, pool_pre_ping=True) if settings.user_read else None
_engine_manga_write = create_async_engine(settings.manga_write, pool_pre_ping=True) if settings.manga_write else None
_engine_manga_read = create_async_engine(settings.manga_read, pool_pre_ping=True) if settings.manga_read else None

# Sessionmakers once
_Session_user_write = async_sessionmaker(_engine_user_write, class_=AsyncSession, expire_on_commit=False) if _engine_user_write else None
_Session_user_read = async_sessionmaker(_engine_user_read, class_=AsyncSession, expire_on_commit=False) if _engine_user_read else None
_Session_manga_write = async_sessionmaker(_engine_manga_write, class_=AsyncSession, expire_on_commit=False) if _engine_manga_write else None
_Session_manga_read = async_sessionmaker(_engine_manga_read, class_=AsyncSession, expire_on_commit=False) if _engine_manga_read else None

# Dependency providers
async def get_user_read_db() -> AsyncGenerator[ClientDatabase, None]:
    async with _Session_user_read() as session:
        yield ClientDatabase(session)

async def get_user_write_db() -> AsyncGenerator[ClientDatabase, None]:
    async with _Session_user_write() as session:
        yield ClientDatabase(session)

async def get_manga_read_db() -> AsyncGenerator[ClientDatabase, None]:
    async with _Session_manga_read() as session:
        yield ClientDatabase(session)

async def get_manga_write_db() -> AsyncGenerator[ClientDatabase, None]:
    async with _Session_manga_write() as session:
        yield ClientDatabase(session)

# Raw session (for FastAPI Users)
async def get_async_user_write_session() -> AsyncGenerator[AsyncSession, None]:
    async with _Session_user_write() as session:
        yield session
