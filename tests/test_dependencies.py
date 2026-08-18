from unittest.mock import AsyncMock, MagicMock

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


class FakeConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


def make_engine(*, execute_side_effect=None):
    connection = MagicMock()
    connection.execute = AsyncMock(
        side_effect=execute_side_effect
    )

    engine = MagicMock()
    engine.connect.return_value = (
        FakeConnectionContext(connection)
    )
    engine.dispose = AsyncMock()

    return engine, connection


async def exhaust_generator(generator):
    with pytest.raises(StopAsyncIteration):
        await anext(generator)


def test_database_runtime_defaults_are_environment_aware(
    monkeypatch,
):
    monkeypatch.setattr(dependencies, "ENV", "prod")
    assert dependencies._default_database_pool_mode() == "null"
    assert (
        dependencies._default_prepared_statement_cache_size()
        == 0
    )

    monkeypatch.setattr(dependencies, "ENV", "dev")
    assert dependencies._default_database_pool_mode() == "queue"
    assert (
        dependencies._default_prepared_statement_cache_size()
        == 100
    )


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


def test_validate_database_config_allows_non_production(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies,
        "ENV",
        "test",
    )

    assert dependencies.validate_database_config() is None


def test_validate_database_config_accepts_complete_production_config(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "user_write",
        "postgresql+asyncpg://user-write",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "user_read",
        "postgresql+asyncpg://user-read",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "manga_write",
        "postgresql+asyncpg://manga-write",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "manga_read",
        "postgresql+asyncpg://manga-read",
    )

    assert dependencies.validate_database_config() is None


def test_validate_database_config_lists_missing_production_urls(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "user_write",
        None,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "user_read",
        "postgresql+asyncpg://user-read",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "manga_write",
        None,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "manga_read",
        "postgresql+asyncpg://manga-read",
    )

    with pytest.raises(
        RuntimeError,
        match="UserWriterDB, MangaWriterDB",
    ):
        dependencies.validate_database_config()


def test_database_engine_kwargs_use_null_pool_for_external_pooler(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies.settings,
        "database_pool_mode",
        "null",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_connect_timeout_seconds",
        4.0,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_command_timeout_seconds",
        12.0,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_prepared_statement_cache_size",
        0,
    )

    kwargs = dependencies._database_engine_kwargs()

    assert kwargs["poolclass"] is dependencies.NullPool
    assert "pool_size" not in kwargs
    assert "max_overflow" not in kwargs
    assert "pool_timeout" not in kwargs
    assert "pool_pre_ping" not in kwargs

    connect_args = kwargs["connect_args"]
    assert connect_args["timeout"] == 4.0
    assert connect_args["command_timeout"] == 12.0
    assert connect_args["prepared_statement_cache_size"] == 0

    name_factory = connect_args[
        "prepared_statement_name_func"
    ]
    first_name = name_factory()
    second_name = name_factory()

    assert first_name.startswith("__asyncpg_")
    assert first_name.endswith("__")
    assert second_name != first_name


def test_database_engine_kwargs_bound_queue_pool(
    monkeypatch,
):
    monkeypatch.setattr(
        dependencies.settings,
        "database_pool_mode",
        "queue",
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_pool_size",
        2,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_max_overflow",
        1,
    )
    monkeypatch.setattr(
        dependencies.settings,
        "database_pool_timeout_seconds",
        6.0,
    )

    kwargs = dependencies._database_engine_kwargs()

    assert kwargs["pool_pre_ping"] is True
    assert kwargs["pool_size"] == 2
    assert kwargs["max_overflow"] == 1
    assert kwargs["pool_timeout"] == 6.0
    assert "poolclass" not in kwargs


def test_create_database_engine_passes_resolved_options(
    monkeypatch,
):
    expected_engine = MagicMock()
    create_engine = MagicMock(
        return_value=expected_engine
    )
    expected_kwargs = {
        "poolclass": dependencies.NullPool,
        "connect_args": {"timeout": 5.0},
    }

    monkeypatch.setattr(
        dependencies,
        "create_async_engine",
        create_engine,
    )
    monkeypatch.setattr(
        dependencies,
        "_database_engine_kwargs",
        lambda: expected_kwargs,
    )

    result = dependencies._create_database_engine(
        "postgresql+asyncpg://database"
    )

    assert result is expected_engine
    create_engine.assert_called_once_with(
        "postgresql+asyncpg://database",
        **expected_kwargs,
    )


@pytest.mark.asyncio
async def test_database_engine_ready_executes_select_one():
    engine, connection = make_engine()

    result = await dependencies._database_engine_ready(
        engine,
        timeout=0.5,
    )

    assert result is True
    connection.execute.assert_awaited_once()
    assert str(
        connection.execute.await_args.args[0]
    ) == "SELECT 1"


@pytest.mark.asyncio
async def test_database_engine_ready_returns_false_without_engine():
    result = await dependencies._database_engine_ready(
        None,
        timeout=0.5,
    )

    assert result is False


@pytest.mark.asyncio
async def test_database_engine_ready_returns_false_on_query_error():
    engine, _ = make_engine(
        execute_side_effect=RuntimeError(
            "database unavailable"
        )
    )

    result = await dependencies._database_engine_ready(
        engine,
        timeout=0.5,
    )

    assert result is False


@pytest.mark.asyncio
async def test_database_connections_ready_requires_every_engine(
    monkeypatch,
):
    engines = tuple(
        (name, MagicMock())
        for name in (
            "user_writer",
            "user_reader",
            "manga_writer",
            "manga_reader",
        )
    )
    probe = AsyncMock(
        side_effect=[True, True, False, True]
    )

    monkeypatch.setattr(
        dependencies,
        "_database_engines",
        lambda: engines,
    )
    monkeypatch.setattr(
        dependencies,
        "_database_engine_ready",
        probe,
    )

    result = await dependencies.database_connections_ready(
        timeout=0.75
    )

    assert result is False
    assert probe.await_count == 4
    assert all(
        call.kwargs == {"timeout": 0.75}
        for call in probe.await_args_list
    )


@pytest.mark.asyncio
async def test_database_connections_ready_uses_configured_timeout(
    monkeypatch,
):
    engines = tuple(
        (name, MagicMock())
        for name in (
            "user_writer",
            "user_reader",
            "manga_writer",
            "manga_reader",
        )
    )
    probe = AsyncMock(return_value=True)

    monkeypatch.setattr(
        dependencies.settings,
        "database_ready_timeout_seconds",
        4.5,
    )
    monkeypatch.setattr(
        dependencies,
        "_database_engines",
        lambda: engines,
    )
    monkeypatch.setattr(
        dependencies,
        "_database_engine_ready",
        probe,
    )

    result = await dependencies.database_connections_ready()

    assert result is True
    assert probe.await_count == 4
    assert all(
        call.kwargs == {"timeout": 4.5}
        for call in probe.await_args_list
    )


@pytest.mark.asyncio
async def test_dispose_database_engines_disposes_every_configured_engine(
    monkeypatch,
):
    engines = [
        make_engine()[0],
        make_engine()[0],
        make_engine()[0],
        make_engine()[0],
    ]

    monkeypatch.setattr(
        dependencies,
        "_database_engines",
        lambda: (
            ("user_writer", engines[0]),
            ("user_reader", engines[1]),
            ("manga_writer", engines[2]),
            ("manga_reader", engines[3]),
        ),
    )

    await dependencies.dispose_database_engines()

    for engine in engines:
        engine.dispose.assert_awaited_once_with()
