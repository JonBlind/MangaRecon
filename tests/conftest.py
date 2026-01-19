import os
from dotenv import load_dotenv

# Make sure we set the env before importing the rest!
# Other modules may not work as intended if we do not mark the env as test!
os.environ["MANGARECON_ENV"] = "test"
load_dotenv(".env.test", override=True)

import asyncio
import logging

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.db.client_db import ClientDatabase

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

@pytest.fixture(scope="session", autouse=True)
def _force_test_env():
    old = os.environ.get("MANGARECON_ENV")
    os.environ["MANGARECON_ENV"] = "test"
    yield
    if old is None:
        os.environ.pop("MANGARECON_ENV", None)
    else:
        os.environ["MANGARECON_ENV"] = old

@pytest.fixture(autouse=True)
def _restore_logging_state():
    # Make caplog reliable even if other tests/modules modify.
    logging.disable(logging.NOTSET)

    root = logging.getLogger()
    if root.level > logging.WARNING:
        root.setLevel(logging.WARNING)

    for name in ("backend", "backend.utils", "backend.utils.errors"):
        lg = logging.getLogger(name)
        lg.disabled = False
        lg.propagate = True
        if lg.level == logging.NOTSET:
            pass

    yield

@pytest.fixture(scope="session")
def test_database_url():
    url = os.getenv("DATABASE_URL_SYNC")
    if not url:
        raise RuntimeError("DATABASE_URL_SYNC is not set")
    return url

@pytest.fixture(scope="session")
def migrated_engine(test_database_url):
    engine = create_async_engine(test_database_url, future=True)

    alembic_cfg = Config("alembic_test.ini")
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.sync_engine.dispose()

@pytest.fixture
async def db_session(migrated_engine):
    Session = async_sessionmaker(
        migrated_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with migrated_engine.connect() as conn:
        outer = await conn.begin()

        async with Session(bind=conn) as session:
            await session.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sess, trans):
                if trans.nested and not trans._parent.nested:
                    sess.begin_nested()

            try:
                yield session
            finally:
                await session.close()
                await outer.rollback()

@pytest.fixture
def client_db(db_session):
    return ClientDatabase(db_session)