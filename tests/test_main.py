from unittest.mock import AsyncMock, MagicMock

import pytest

from backend import main


@pytest.mark.asyncio
async def test_lifespan_test_environment_sets_ready_without_redis(
    monkeypatch,
):
    app = MagicMock()
    get_cache = MagicMock()
    storage_ready = AsyncMock()

    monkeypatch.setattr(main, "ENV", "test")
    monkeypatch.setattr(
        main,
        "get_redis_cache",
        get_cache,
    )
    monkeypatch.setattr(
        main,
        "rate_limit_storage_ready",
        storage_ready,
    )
    monkeypatch.setenv(
        "RATELIMIT_CHECK_SECONDS",
        "30",
    )

    async with main.lifespan(app):
        assert (
            app.state.rate_limit_storage_ready
            is True
        )
        assert app.state.rate_limit_last_log == 0.0
        assert app.state.rate_limit_last_check == 0.0
        assert (
            app.state.rate_limit_check_interval
            == 30.0
        )

    get_cache.assert_not_called()
    storage_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_dev_environment_does_not_create_redis(
    monkeypatch,
):
    app = MagicMock()
    get_cache = MagicMock()
    storage_ready = AsyncMock()

    monkeypatch.setattr(main, "ENV", "dev")
    monkeypatch.setattr(
        main,
        "get_redis_cache",
        get_cache,
    )
    monkeypatch.setattr(
        main,
        "rate_limit_storage_ready",
        storage_ready,
    )

    async with main.lifespan(app):
        assert (
            app.state.rate_limit_storage_ready
            is True
        )

    get_cache.assert_not_called()
    storage_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_lifespan_prod_checks_storage_and_closes_redis(
    monkeypatch,
):
    app = MagicMock()

    redis_cache = MagicMock()
    redis_cache.close = AsyncMock()

    get_cache = MagicMock(
        return_value=redis_cache
    )
    storage_ready = AsyncMock(
        return_value=False
    )

    monkeypatch.setattr(main, "ENV", "prod")
    monkeypatch.setattr(
        main,
        "get_redis_cache",
        get_cache,
    )
    monkeypatch.setattr(
        main,
        "rate_limit_storage_ready",
        storage_ready,
    )
    monkeypatch.setenv(
        "RATELIMIT_CHECK_SECONDS",
        "12.5",
    )

    async with main.lifespan(app):
        assert (
            app.state.rate_limit_storage_ready
            is False
        )
        assert (
            app.state.rate_limit_check_interval
            == 12.5
        )

        redis_cache.close.assert_not_awaited()

    get_cache.assert_called_once_with()
    storage_ready.assert_awaited_once_with()
    redis_cache.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_lifespan_non_prod_deployment_uses_redis_but_skips_storage_check(
    monkeypatch,
):
    app = MagicMock()

    redis_cache = MagicMock()
    redis_cache.close = AsyncMock()

    get_cache = MagicMock(
        return_value=redis_cache
    )
    storage_ready = AsyncMock()

    monkeypatch.setattr(main, "ENV", "staging")
    monkeypatch.setattr(
        main,
        "get_redis_cache",
        get_cache,
    )
    monkeypatch.setattr(
        main,
        "rate_limit_storage_ready",
        storage_ready,
    )

    async with main.lifespan(app):
        assert (
            app.state.rate_limit_storage_ready
            is True
        )

    get_cache.assert_called_once_with()
    storage_ready.assert_not_awaited()
    redis_cache.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_lifespan_closes_redis_when_application_raises(
    monkeypatch,
):
    app = MagicMock()

    redis_cache = MagicMock()
    redis_cache.close = AsyncMock()

    monkeypatch.setattr(main, "ENV", "prod")
    monkeypatch.setattr(
        main,
        "get_redis_cache",
        MagicMock(return_value=redis_cache),
    )
    monkeypatch.setattr(
        main,
        "rate_limit_storage_ready",
        AsyncMock(return_value=True),
    )

    with pytest.raises(
        RuntimeError,
        match="application failed",
    ):
        async with main.lifespan(app):
            raise RuntimeError(
                "application failed"
            )

    redis_cache.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_lifespan_uses_default_check_interval(
    monkeypatch,
):
    app = MagicMock()

    monkeypatch.setattr(main, "ENV", "test")
    monkeypatch.delenv(
        "RATELIMIT_CHECK_SECONDS",
        raising=False,
    )

    async with main.lifespan(app):
        assert (
            app.state.rate_limit_check_interval
            == 15.0
        )


def test_create_app_configures_application_in_test_environment(
    monkeypatch,
):
    app = MagicMock()

    fastapi_constructor = MagicMock(
        return_value=app
    )
    register_errors = MagicMock()
    validate_config = MagicMock()
    register_limiter = MagicMock()

    monkeypatch.setattr(
        main,
        "FastAPI",
        fastapi_constructor,
    )
    monkeypatch.setattr(
        main,
        "register_exception_handlers",
        register_errors,
    )
    monkeypatch.setattr(
        main,
        "validate_rate_limit_config",
        validate_config,
    )
    monkeypatch.setattr(
        main,
        "register_rate_limiter",
        register_limiter,
    )
    monkeypatch.setattr(main, "ENV", "test")

    result = main.create_app()

    assert result is app

    fastapi_constructor.assert_called_once_with(
        lifespan=main.lifespan,
        debug=main.settings.debug,
        redirect_slashes=False,
    )

    register_errors.assert_called_once_with(app)
    validate_config.assert_called_once_with()
    register_limiter.assert_not_called()

    app.add_middleware.assert_called_once_with(
        main.CORSMiddleware,
        allow_origins=main.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    expected_routers = [
        main.auth_routes.router,
        main.collection_routes.router,
        main.manga_routes.router,
        main.rating_routes.router,
        main.recommendation_routes.router,
        main.profile_routes.router,
        main.metadata_routes.router,
        main.system_routes.router,
    ]

    assert [
        call.args[0]
        for call in app.include_router.call_args_list
    ] == expected_routers


def test_create_app_registers_rate_limiter_outside_test(
    monkeypatch,
):
    app = MagicMock()

    monkeypatch.setattr(
        main,
        "FastAPI",
        MagicMock(return_value=app),
    )
    monkeypatch.setattr(
        main,
        "register_exception_handlers",
        MagicMock(),
    )
    monkeypatch.setattr(
        main,
        "validate_rate_limit_config",
        MagicMock(),
    )

    register_limiter = MagicMock()
    monkeypatch.setattr(
        main,
        "register_rate_limiter",
        register_limiter,
    )
    monkeypatch.setattr(main, "ENV", "prod")

    result = main.create_app()

    assert result is app
    register_limiter.assert_called_once_with(app)


def test_create_app_validates_rate_limit_config_before_registering_limiter(
    monkeypatch,
):
    app = MagicMock()

    events = []

    monkeypatch.setattr(
        main,
        "FastAPI",
        MagicMock(return_value=app),
    )
    monkeypatch.setattr(
        main,
        "register_exception_handlers",
        lambda _app: events.append(
            "exceptions"
        ),
    )
    monkeypatch.setattr(
        main,
        "validate_rate_limit_config",
        lambda: events.append(
            "validate"
        ),
    )
    monkeypatch.setattr(
        main,
        "register_rate_limiter",
        lambda _app: events.append(
            "limiter"
        ),
    )
    monkeypatch.setattr(main, "ENV", "prod")

    main.create_app()

    assert events == [
        "exceptions",
        "validate",
        "limiter",
    ]


def test_create_app_propagates_rate_limit_validation_error(
    monkeypatch,
):
    app = MagicMock()

    monkeypatch.setattr(
        main,
        "FastAPI",
        MagicMock(return_value=app),
    )
    monkeypatch.setattr(
        main,
        "register_exception_handlers",
        MagicMock(),
    )
    monkeypatch.setattr(
        main,
        "validate_rate_limit_config",
        MagicMock(
            side_effect=RuntimeError(
                "invalid rate-limit configuration"
            )
        ),
    )

    register_limiter = MagicMock()
    monkeypatch.setattr(
        main,
        "register_rate_limiter",
        register_limiter,
    )
    monkeypatch.setattr(main, "ENV", "prod")

    with pytest.raises(
        RuntimeError,
        match=(
            "invalid rate-limit configuration"
        ),
    ):
        main.create_app()

    register_limiter.assert_not_called()
    app.add_middleware.assert_not_called()
    app.include_router.assert_not_called()