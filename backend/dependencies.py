'''
Dependency wiring for database access.

Provides read/write AsyncSession for the User and Manga domains,
yields `ClientDatabase` for those sessions, and exposes a
user-write session for `fastapi-users` integration.
'''

from typing import AsyncGenerator, Optional
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase

class Settings(BaseSettings):
    '''
    Application settings for async database connections (asyncpg URLs).

    Attributes:
        user_write (str | None): DSN for user-domain write engine
            (env alias: "UserWriterDB").
        user_read (str | None): DSN for user-domain read engine
            (env alias: "UserReaderDB").
        manga_write (str | None): DSN for manga-domain write engine
            (env alias: "MangaWriterDB").
        manga_read (str | None): DSN for manga-domain read engine
            (env alias: "MangaReaderDB").

    Notes:
        - Values are loaded from `.env` (utf-8) via pydantic-settings.
        - Unknown environment variables are ignored (`extra="ignore"`).
    '''
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore")
    
    user_write: Optional[str] = Field(None, validation_alias=AliasChoices("UserWriterDB"))
    user_read: Optional[str] = Field(None, validation_alias=AliasChoices("UserReaderDB"))
    manga_write: Optional[str] = Field(None, validation_alias=AliasChoices("MangaWriterDB"))
    manga_read: Optional[str] = Field(None, validation_alias=AliasChoices("MangaReaderDB"))

settings = Settings()

# Create async engines (if the corresponding DSN is not provided, the engine remains None).
_engine_user_write = create_async_engine(settings.user_write, pool_pre_ping=True) if settings.user_write else None
_engine_user_read = create_async_engine(settings.user_read, pool_pre_ping=True) if settings.user_read else None
_engine_manga_write = create_async_engine(settings.manga_write, pool_pre_ping=True) if settings.manga_write else None
_engine_manga_read = create_async_engine(settings.manga_read, pool_pre_ping=True) if settings.manga_read else None

# Session factories (expire_on_commit=False ensures objects remain usable after commit).
_Session_user_write = async_sessionmaker(_engine_user_write, class_=AsyncSession, expire_on_commit=False) if _engine_user_write else None
_Session_user_read = async_sessionmaker(_engine_user_read, class_=AsyncSession, expire_on_commit=False) if _engine_user_read else None
_Session_manga_write = async_sessionmaker(_engine_manga_write, class_=AsyncSession, expire_on_commit=False) if _engine_manga_write else None
_Session_manga_read = async_sessionmaker(_engine_manga_read, class_=AsyncSession, expire_on_commit=False) if _engine_manga_read else None

# Dependency providers
async def get_user_read_db() -> AsyncGenerator[ClientReadDatabase, None]:
    '''
    Yield a `ClientDatabase` bound to the **User read** AsyncSession.

    Designed for read-only endpoints in the user domain. The session is opened
    at dependency entry and closed automatically when the request finishes.

    Returns:
        Async generator yielding a `ClientDatabase` wrapper tied to the user
        read session (closes on exit).
    '''
    async with _Session_user_read() as session:
        yield ClientReadDatabase(session)

async def get_user_write_db() -> AsyncGenerator[ClientWriteDatabase, None]:
    '''
    Yield a `ClientDatabase` bound to the **User write** AsyncSession.

    Use this for endpoints that **mutate** user-domain data. The session is
    request-scoped and cleaned up after the handler returns.

    Returns:
        Async generator yielding a `ClientDatabase` wrapper tied to the user
        write session (closes on exit).
    '''
    async with _Session_user_write() as session:
        yield ClientWriteDatabase(session)

async def get_manga_read_db() -> AsyncGenerator[ClientReadDatabase, None]:
    '''
    Yield a `ClientDatabase` bound to the **Manga read** AsyncSession.

    Use for read-only operations across manga metadata (titles, genres, tags,
    demographics, etc.). The session is request-scoped and disposed on exit.

    Returns:
        Async generator yielding a `ClientDatabase` wrapper tied to the manga
        read session (closes on exit).
    '''
    async with _Session_manga_read() as session:
        yield ClientReadDatabase(session)

async def get_manga_write_db() -> AsyncGenerator[ClientWriteDatabase, None]:
    '''
    Yield a `ClientDatabase` bound to the **Manga write** AsyncSession.

    Use for operations that modify manga-domain data. The session is opened
    for the lifetime of the request and closed automatically after.

    Returns:
        Async generator yielding a `ClientDatabase` wrapper tied to the manga
        write session (closes on exit).
    '''
    async with _Session_manga_write() as session:
        yield ClientWriteDatabase(session)

# Raw session to provide FastAPI User access.
async def get_async_user_write_session() -> AsyncGenerator[AsyncSession, None]:
    '''
    Yield a raw **User write** `AsyncSession` (for FastAPI Users internals).

    This bypasses the DB wrapper and provides a plain SQLAlchemy AsyncSession
    for the authentication system’s adapters/managers that expect direct access.

    Returns:
        Async generator yielding an `AsyncSession` bound to the user write engine
        (closes on exit).
    '''
    async with _Session_user_write() as session:
        yield session