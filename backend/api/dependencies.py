import collections.abc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.api.client_db import ClientDatabase
import os
import dotenv
import collections

dotenv.load_dotenv

URLS = {
    "user_write": os.getenv("UserWriterDB"),
    "user_read": os.getenv("UserReaderDB"),
    "manga_write": os.getenv("MangaWriterDB"),
    "manga_read": os.getenv("MangaReaderDB")
}
 
def get_db_url_by_role(role: str) -> str:
    '''
    Returns the URL for the database stored in the env file based on the role inputted.

    Args:
        role (str): Role to get a URL for.
    Returns:
        str: databse URL for the respective role.

    '''
    if role not in URLS:
        raise ValueError(f"Following Role Does Not Exist in supported Structure {role}")
    else:
        return URLS[role]
    
def get_session_for_role(role: str) -> async_sessionmaker:
    '''
    Create an async session for the database role

    Args:
        role (str): Role for the DB to access and create a session for.

    Returns:
        async_sessionmaker: An async session of the db with the respective role. 
    '''
    url = get_db_url_by_role(role)
    engine = create_async_engine(url, echo=False)
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

async def get_db(role:str) -> collections.abc.AsyncGenerator[ClientDatabase, None]:
    '''
    FastAPI dependency that provides a ClientDatabase Instance tied to the
    async session based on the provided role.
    '''
    SessionLocal = get_session_for_role(role)
    async with SessionLocal() as session:
        yield ClientDatabase(session)