from typing import AsyncGenerator, Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.client_db import ClientDatabase

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore")
    
    user_write: Optional[str] = Field(None, validation_alias=AliasChoices("UserWriterDB"))
    user_read:  Optional[str] = Field(None, validation_alias=AliasChoices("UserReaderDB"))
    manga_write:Optional[str] = Field(None, validation_alias=AliasChoices("MangaWriterDB"))
    manga_read: Optional[str] = Field(None, validation_alias=AliasChoices("MangaReaderDB"))

settings = Settings()

# Build engines
_engine_user_write = create_async_engine(settings.user_write, pool_pre_ping=True) if settings.user_write else None
_engine_user_read = create_async_engine(settings.user_read, pool_pre_ping=True) if settings.user_read else None
_engine_manga_write = create_async_engine(settings.manga_write, pool_pre_ping=True) if settings.manga_write else None
_engine_manga_read = create_async_engine(settings.manga_read, pool_pre_ping=True) if settings.manga_read else None

# Sessionmakers
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
