import collections
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.db.client_db import ClientDatabase
import os
import dotenv

dotenv.load_dotenv()

DB_URLS = {
    "user_write": os.getenv("UserWriterDB"),
    "user_read": os.getenv("UserReaderDB"),
    "manga_write": os.getenv("MangaWriterDB"),
    "manga_read": os.getenv("MangaReaderDB")
}
 
def get_sessionmaker(role: str) -> async_sessionmaker[AsyncSession]:
    '''
    Returns a session for the database depending on the inputted role.

    Args:
        role (str): Role to get the URL and sign in for.
    Returns:
        str: databse URL for the respective role.

    '''
    if role not in DB_URLS or DB_URLS[role] is None:
        raise ValueError(f"Following Role Does Not Exist in supported Structure {role}")
    else:
        engine = create_async_engine(DB_URLS[role], echo=False)
        return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    

async def get_client_db_for_role(role:str) -> AsyncGenerator[ClientDatabase, None]:
    '''
    FastAPI dependency that provides a ClientDatabase Instance tied to the
    async session based on the provided role.
    '''
    SessionLocal = get_sessionmaker(role)
    async with SessionLocal() as session:
        yield ClientDatabase(session)


async def get_user_read_db() -> collections.abc.AsyncGenerator[ClientDatabase, None]:
    SessionLocal = get_sessionmaker("user_read")
    async with SessionLocal() as session:
        yield ClientDatabase(session)


async def get_user_write_db() -> collections.abc.AsyncGenerator[ClientDatabase, None]:
    SessionLocal = get_sessionmaker("user_write")
    async with SessionLocal() as session:
        yield ClientDatabase(session)

async def get_manga_read_db() -> collections.abc.AsyncGenerator[ClientDatabase, None]:
    SessionLocal = get_sessionmaker("manga_read")
    async with SessionLocal() as session:
        yield ClientDatabase(session)

async def get_manga_write_db() -> collections.abc.AsyncGenerator[ClientDatabase, None]:
    SessionLocal = get_sessionmaker("manga_write")
    async with SessionLocal() as session:
        yield ClientDatabase(session)