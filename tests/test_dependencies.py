from unittest.mock import MagicMock

import pytest

from backend import dependencies
from backend.db.client_db import (
    ClientReadDatabase,
    ClientWriteDatabase,
)


class FakeAsyncSessionContext:
    """
    Async context manager returned by a fake session factory.
    """

    def __init__(self, session):
        self.session = session
        self.entered = False
        self.exited = False
        self.exit_args = None

    async def __aenter__(self):
        self.entered = True
        return self.session

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.exited = True
        self.exit_args = (
            exc_type,
            exc,
            traceback,
        )
        return False


class FakeSessionFactory:
    """
    Callable replacement for async_sessionmaker.
    """

    def __init__(self, session):
        self.session = session
        self.call_count = 0
        self.contexts = []

    def __call__(self):
        self.call_count += 1

        context = FakeAsyncSessionContext(
            self.session
        )
        self.contexts.append(context)

        return context


async def exhaust_generator(generator):
    with pytest.raises(StopAsyncIteration):
        await anext(generator)


@pytest.mark.asyncio
async def test_get_user_read_db_yields_read_wrapper(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        factory,
    )

    generator = dependencies.get_user_read_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientReadDatabase,
    )
    assert not isinstance(
        result,
        ClientWriteDatabase,
    )
    assert result._session is session

    assert factory.call_count == 1
    assert factory.contexts[0].entered is True
    assert factory.contexts[0].exited is False

    await exhaust_generator(generator)

    assert factory.contexts[0].exited is True
    assert factory.contexts[0].exit_args == (
        None,
        None,
        None,
    )


@pytest.mark.asyncio
async def test_get_user_write_db_yields_write_wrapper(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_write",
        factory,
    )

    generator = dependencies.get_user_write_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientWriteDatabase,
    )
    assert result._session is session

    assert factory.call_count == 1
    assert factory.contexts[0].entered is True

    await exhaust_generator(generator)

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_manga_read_db_yields_read_wrapper(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        factory,
    )

    generator = dependencies.get_manga_read_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientReadDatabase,
    )
    assert not isinstance(
        result,
        ClientWriteDatabase,
    )
    assert result._session is session

    await exhaust_generator(generator)

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_manga_write_db_yields_write_wrapper(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_write",
        factory,
    )

    generator = dependencies.get_manga_write_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientWriteDatabase,
    )
    assert result._session is session

    await exhaust_generator(generator)

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_async_user_write_session_yields_raw_session(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_write",
        factory,
    )

    generator = (
        dependencies.get_async_user_write_session()
    )

    result = await anext(generator)

    assert result is session
    assert not isinstance(
        result,
        ClientReadDatabase,
    )
    assert factory.contexts[0].entered is True

    await exhaust_generator(generator)

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_user_read_db_closes_context_when_generator_is_closed(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        factory,
    )

    generator = dependencies.get_user_read_db()

    await anext(generator)

    await generator.aclose()

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_user_write_db_closes_context_when_generator_is_closed(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_write",
        factory,
    )

    generator = dependencies.get_user_write_db()

    await anext(generator)

    await generator.aclose()

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_manga_read_db_closes_context_when_generator_is_closed(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        factory,
    )

    generator = dependencies.get_manga_read_db()

    await anext(generator)

    await generator.aclose()

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_manga_write_db_closes_context_when_generator_is_closed(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_write",
        factory,
    )

    generator = dependencies.get_manga_write_db()

    await anext(generator)

    await generator.aclose()

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_raw_user_session_closes_context_when_generator_is_closed(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_write",
        factory,
    )

    generator = (
        dependencies.get_async_user_write_session()
    )

    await anext(generator)

    await generator.aclose()

    assert factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_public_read_db_prefers_manga_read_session(
    monkeypatch,
):
    manga_session = MagicMock()
    user_session = MagicMock()

    manga_factory = FakeSessionFactory(
        manga_session
    )
    user_factory = FakeSessionFactory(
        user_session
    )

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        manga_factory,
    )
    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        user_factory,
    )

    generator = dependencies.get_public_read_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientReadDatabase,
    )
    assert result._session is manga_session

    assert manga_factory.call_count == 1
    assert user_factory.call_count == 0

    await exhaust_generator(generator)

    assert manga_factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_public_read_db_falls_back_to_user_read_session(
    monkeypatch,
):
    user_session = MagicMock()
    user_factory = FakeSessionFactory(
        user_session
    )

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        None,
    )
    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        user_factory,
    )

    generator = dependencies.get_public_read_db()

    result = await anext(generator)

    assert isinstance(
        result,
        ClientReadDatabase,
    )
    assert result._session is user_session

    assert user_factory.call_count == 1

    await exhaust_generator(generator)

    assert user_factory.contexts[0].exited is True


@pytest.mark.asyncio
async def test_get_public_read_db_raises_when_no_read_session_configured(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        None,
    )
    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        None,
    )

    generator = dependencies.get_public_read_db()

    with pytest.raises(
        RuntimeError,
        match=(
            "No public read database session "
            "configured"
        ),
    ):
        await anext(generator)


@pytest.mark.asyncio
async def test_get_public_read_db_does_not_fall_back_when_manga_context_fails(
    monkeypatch,
):
    class FailingFactory:
        def __call__(self):
            raise RuntimeError(
                "manga session creation failed"
            )

    user_factory = FakeSessionFactory(
        MagicMock()
    )

    monkeypatch.setattr(
        dependencies,
        "_Session_manga_read",
        FailingFactory(),
    )
    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        user_factory,
    )

    generator = dependencies.get_public_read_db()

    with pytest.raises(
        RuntimeError,
        match="manga session creation failed",
    ):
        await anext(generator)

    assert user_factory.call_count == 0


@pytest.mark.asyncio
async def test_dependency_context_receives_exception_on_generator_throw(
    monkeypatch,
):
    session = MagicMock()
    factory = FakeSessionFactory(session)

    monkeypatch.setattr(
        dependencies,
        "_Session_user_read",
        factory,
    )

    generator = dependencies.get_user_read_db()

    await anext(generator)

    with pytest.raises(
        RuntimeError,
        match="route failed",
    ):
        await generator.athrow(
            RuntimeError("route failed")
        )

    context = factory.contexts[0]

    assert context.exited is True
    assert context.exit_args[0] is RuntimeError
    assert str(context.exit_args[1]) == (
        "route failed"
    )