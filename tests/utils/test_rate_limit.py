import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.utils import rate_limit


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


def make_request(
    path="/mangas",
    *,
    ready=True,
    last_check=0.0,
    check_interval=15.0,
    last_log=0.0,
):
    state = SimpleNamespace(
        rate_limit_storage_ready=ready,
        rate_limit_last_check=last_check,
        rate_limit_check_interval=check_interval,
        rate_limit_last_log=last_log,
    )

    app = SimpleNamespace(state=state)

    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        app=app,
    )


def make_middleware(middleware_class):
    return middleware_class(MagicMock())


@pytest.mark.parametrize(
    "environment",
    [
        "dev",
        "test",
    ],
)
def test_get_storage_uri_uses_memory_in_non_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )
    monkeypatch.delenv(
        "RATELIMIT_STORAGE_URI",
        raising=False,
    )

    assert rate_limit._get_storage_uri() == "memory://"


def test_get_storage_uri_returns_configured_production_uri(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost:6379/1",
    )

    assert rate_limit._get_storage_uri() == (
        "redis://localhost:6379/1"
    )


def test_get_storage_uri_rejects_missing_production_uri(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.delenv(
        "RATELIMIT_STORAGE_URI",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "RATELIMIT_STORAGE_URI must be set "
            "when MANGARECON_ENV=prod"
        ),
    ):
        rate_limit._get_storage_uri()


@pytest.mark.parametrize(
    "environment",
    [
        "dev",
        "test",
    ],
)
def test_validate_rate_limit_config_allows_non_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )
    monkeypatch.delenv(
        "RATELIMIT_STORAGE_URI",
        raising=False,
    )

    assert rate_limit.validate_rate_limit_config() is None


def test_validate_rate_limit_config_accepts_production_uri(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost:6379",
    )

    assert rate_limit.validate_rate_limit_config() is None


def test_validate_rate_limit_config_rejects_missing_production_uri(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.delenv(
        "RATELIMIT_STORAGE_URI",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "ENV=prod requires "
            "RATELIMIT_STORAGE_URI"
        ),
    ):
        rate_limit.validate_rate_limit_config()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment",
    [
        "dev",
        "test",
    ],
)
async def test_storage_ready_is_true_without_redis_in_non_production(
    monkeypatch,
    environment,
):
    from_url = MagicMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        from_url,
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is True
    from_url.assert_not_called()


@pytest.mark.asyncio
async def test_storage_ready_is_false_when_uri_missing(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.delenv(
        "RATELIMIT_STORAGE_URI",
        raising=False,
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "uri",
    [
        "memory://",
        "postgresql://database",
        "custom://storage",
    ],
)
async def test_storage_ready_accepts_non_redis_storage_without_ping(
    monkeypatch,
    uri,
):
    from_url = MagicMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        uri,
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        from_url,
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is True
    from_url.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "ping_result",
    [
        True,
        1,
    ],
)
async def test_storage_ready_pings_redis_and_closes_client(
    monkeypatch,
    ping_result,
):
    client = MagicMock()
    client.ping = AsyncMock(
        return_value=ping_result
    )
    client.aclose = AsyncMock()

    from_url = MagicMock(
        return_value=client
    )

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost:6379/2",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        from_url,
    )

    result = await rate_limit.rate_limit_storage_ready(
        timeout=0.75
    )

    assert result is True

    from_url.assert_called_once_with(
        "redis://localhost:6379/2",
        decode_responses=True,
        socket_connect_timeout=0.75,
        socket_timeout=0.75,
    )
    client.ping.assert_awaited_once_with()
    client.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_storage_ready_returns_false_when_ping_is_false(
    monkeypatch,
):
    client = MagicMock()
    client.ping = AsyncMock(
        return_value=False
    )
    client.aclose = AsyncMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "rediss://redis.example",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        MagicMock(return_value=client),
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False
    client.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_storage_ready_returns_false_and_closes_after_ping_error(
    monkeypatch,
):
    client = MagicMock()
    client.ping = AsyncMock(
        side_effect=RuntimeError("Redis unavailable")
    )
    client.aclose = AsyncMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        MagicMock(return_value=client),
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False
    client.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_storage_ready_suppresses_close_error(
    monkeypatch,
):
    client = MagicMock()
    client.ping = AsyncMock(
        return_value=True
    )
    client.aclose = AsyncMock(
        side_effect=RuntimeError("close failed")
    )

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        MagicMock(return_value=client),
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is True


@pytest.mark.asyncio
async def test_storage_ready_returns_false_when_client_creation_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "RATELIMIT_STORAGE_URI",
        "redis://localhost",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        MagicMock(
            side_effect=RuntimeError("creation failed")
        ),
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "environment",
    [
        "dev",
        "test",
    ],
)
async def test_maintenance_middleware_bypasses_checks_in_non_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        ready=False
    )
    expected = MagicMock()
    call_next = AsyncMock(
        return_value=expected
    )

    result = await middleware.dispatch(
        request,
        call_next,
    )

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_maintenance_health_endpoint_always_returns_200(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        "/healthz",
        ready=False,
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(
        request,
        call_next,
    )

    assert response.status_code == 200
    assert response_json(response) == {
        "message": "MangaRecon API is running."
    }
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_maintenance_ready_endpoint_returns_200_when_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        "/readyz",
        ready=True,
    )

    response = await middleware.dispatch(
        request,
        AsyncMock(),
    )

    assert response.status_code == 200
    assert response_json(response) == {
        "message": "MangaRecon API is ready"
    }


@pytest.mark.asyncio
async def test_maintenance_ready_endpoint_returns_503_when_unready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=10.0),
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        "/readyz",
        ready=False,
        last_check=5.0,
        check_interval=15.0,
    )

    response = await middleware.dispatch(
        request,
        AsyncMock(),
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "15"
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Service unavailable",
        "detail": "TEMPORARILY_UNAVAILABLE",
    }


@pytest.mark.asyncio
async def test_maintenance_allows_normal_request_when_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        ready=True
    )
    expected = MagicMock()
    call_next = AsyncMock(
        return_value=expected
    )

    result = await middleware.dispatch(
        request,
        call_next,
    )

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_maintenance_blocks_normal_request_when_unready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=10.0),
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        ready=False,
        last_check=5.0,
        check_interval=15.0,
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(
        request,
        call_next,
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "15"
    assert response_json(response)["detail"] == (
        "TEMPORARILY_UNAVAILABLE"
    )
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_maintenance_rechecks_storage_after_interval_and_recovers(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=30.0),
    )

    readiness_check = AsyncMock(
        return_value=True
    )
    monkeypatch.setattr(
        rate_limit,
        "rate_limit_storage_ready",
        readiness_check,
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        ready=False,
        last_check=10.0,
        check_interval=15.0,
    )
    expected = MagicMock()
    call_next = AsyncMock(
        return_value=expected
    )

    result = await middleware.dispatch(
        request,
        call_next,
    )

    assert result is expected
    assert (
        request.app.state.rate_limit_last_check
        == 30.0
    )
    assert (
        request.app.state.rate_limit_storage_ready
        is True
    )

    readiness_check.assert_awaited_once_with()
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_maintenance_rechecks_storage_and_remains_unready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=30.0),
    )

    readiness_check = AsyncMock(
        return_value=False
    )
    monkeypatch.setattr(
        rate_limit,
        "rate_limit_storage_ready",
        readiness_check,
    )

    middleware = make_middleware(
        rate_limit.MaintenanceModeMiddleware
    )
    request = make_request(
        ready=False,
        last_check=0.0,
        check_interval=15.0,
    )

    response = await middleware.dispatch(
        request,
        AsyncMock(),
    )

    assert response.status_code == 503
    assert (
        request.app.state.rate_limit_storage_ready
        is False
    )
    readiness_check.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_safe_middleware_returns_downstream_response():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request()
    expected = MagicMock()
    call_next = AsyncMock(
        return_value=expected
    )

    result = await middleware.dispatch(
        request,
        call_next,
    )

    assert result is expected


@pytest.mark.asyncio
async def test_safe_middleware_converts_rate_limit_exception_to_429(
    monkeypatch,
):
    class FakeRateLimitExceeded(Exception):
        pass

    monkeypatch.setattr(
        rate_limit,
        "RateLimitExceeded",
        FakeRateLimitExceeded,
    )

    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request()
    call_next = AsyncMock(
        side_effect=FakeRateLimitExceeded()
    )

    response = await middleware.dispatch(
        request,
        call_next,
    )

    assert response.status_code == 429
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Rate limit exceeded",
        "detail": "RATE_LIMIT_EXCEEDED",
    }


@pytest.mark.asyncio
async def test_safe_middleware_converts_detail_attribute_crash_to_503(
    monkeypatch,
):
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request()

    log_crash = MagicMock()
    monkeypatch.setattr(
        middleware,
        "_log_slowapi_crash",
        log_crash,
    )

    exception = AttributeError(
        "'NoneType' object has no attribute 'detail'"
    )

    response = await middleware.dispatch(
        request,
        AsyncMock(side_effect=exception),
    )

    assert response.status_code == 503
    assert response_json(response)["detail"] == (
        "RATE_LIMIT_UNAVAILABLE"
    )
    log_crash.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_safe_middleware_converts_connection_error_to_503(
    monkeypatch,
):
    class ConnectionError(Exception):
        pass

    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request()

    log_down = MagicMock()
    monkeypatch.setattr(
        middleware,
        "_log_limiter_down",
        log_down,
    )

    response = await middleware.dispatch(
        request,
        AsyncMock(
            side_effect=ConnectionError(
                "Redis unavailable"
            )
        ),
    )

    assert response.status_code == 503
    assert response_json(response)["detail"] == (
        "RATE_LIMIT_UNAVAILABLE"
    )
    log_down.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_safe_middleware_reraises_unrecognized_exception():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    with pytest.raises(
        ValueError,
        match="application failure",
    ):
        await middleware.dispatch(
            make_request(),
            AsyncMock(
                side_effect=ValueError(
                    "application failure"
                )
            ),
        )


def test_has_detail_attribute_error_detects_direct_error():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    assert middleware._has_detail_attribute_error(
        AttributeError(
            "object has no attribute 'detail'"
        )
    ) is True


def test_has_detail_attribute_error_returns_false_for_other_errors():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    assert middleware._has_detail_attribute_error(
        AttributeError(
            "object has no attribute 'status'"
        )
    ) is False


def test_has_connection_error_uses_exception_class_name():
    class ConnectionError(Exception):
        pass

    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    assert middleware._has_connection_error(
        ConnectionError("down")
    ) is True
    assert middleware._has_connection_error(
        RuntimeError("down")
    ) is False


def test_iter_exceptions_flattens_nested_exception_groups():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    nested = ExceptionGroup(
        "outer",
        [
            ValueError("first"),
            ExceptionGroup(
                "inner",
                [
                    RuntimeError("second"),
                    AttributeError(
                        "object has no attribute 'detail'"
                    ),
                ],
            ),
        ],
    )

    results = list(
        middleware._iter_exceptions(nested)
    )

    assert nested in results
    assert any(
        isinstance(exc, ValueError)
        for exc in results
    )
    assert any(
        isinstance(exc, RuntimeError)
        for exc in results
    )
    assert any(
        isinstance(exc, AttributeError)
        for exc in results
    )


def test_iter_exceptions_handles_plain_exception():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    exception = RuntimeError("plain")

    assert list(
        middleware._iter_exceptions(exception)
    ) == [exception]


def test_log_limiter_down_logs_after_interval(
    monkeypatch,
):
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request(
        last_log=10.0,
        check_interval=15.0,
    )

    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=30.0),
    )

    warning = MagicMock()
    monkeypatch.setattr(
        rate_limit.logger,
        "warning",
        warning,
    )

    middleware._log_limiter_down(request)

    assert request.app.state.rate_limit_last_log == 30.0
    warning.assert_called_once_with(
        "Rate limit storage connection failed "
        "(Redis unreachable)."
    )


def test_log_limiter_down_throttles_repeated_logs(
    monkeypatch,
):
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request(
        last_log=20.0,
        check_interval=15.0,
    )

    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=30.0),
    )

    warning = MagicMock()
    monkeypatch.setattr(
        rate_limit.logger,
        "warning",
        warning,
    )

    middleware._log_limiter_down(request)

    assert request.app.state.rate_limit_last_log == 20.0
    warning.assert_not_called()


def test_log_slowapi_crash_logs_after_interval(
    monkeypatch,
):
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request(
        last_log=0.0,
        check_interval=15.0,
    )

    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=20.0),
    )

    warning = MagicMock()
    monkeypatch.setattr(
        rate_limit.logger,
        "warning",
        warning,
    )

    middleware._log_slowapi_crash(request)

    assert request.app.state.rate_limit_last_log == 20.0
    warning.assert_called_once_with(
        "SlowAPI rate limiter error handler crashed; "
        "returning 503."
    )


def test_log_slowapi_crash_throttles_repeated_logs(
    monkeypatch,
):
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )
    request = make_request(
        last_log=20.0,
        check_interval=15.0,
    )

    monkeypatch.setattr(
        rate_limit.time,
        "monotonic",
        MagicMock(return_value=25.0),
    )

    warning = MagicMock()
    monkeypatch.setattr(
        rate_limit.logger,
        "warning",
        warning,
    )

    middleware._log_slowapi_crash(request)

    warning.assert_not_called()


@pytest.mark.parametrize(
    "environment",
    [
        "dev",
        "test",
    ],
)
def test_register_rate_limiter_disables_middleware_in_non_production(
    monkeypatch,
    environment,
):
    app = MagicMock()
    log_info = MagicMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )
    monkeypatch.setattr(
        rate_limit.logger,
        "info",
        log_info,
    )

    result = rate_limit.register_rate_limiter(app)

    assert result is None
    assert app.state.limiter is rate_limit.limiter
    app.add_middleware.assert_not_called()

    log_info.assert_called_once_with(
        "Rate limiter disabled (ENV=%s).",
        environment,
    )


def test_register_rate_limiter_adds_all_production_middleware(
    monkeypatch,
):
    app = MagicMock()
    log_info = MagicMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setattr(
        rate_limit,
        "_storage_uri",
        "redis://redis.example",
    )
    monkeypatch.setattr(
        rate_limit.logger,
        "info",
        log_info,
    )

    result = rate_limit.register_rate_limiter(app)

    assert result is None
    assert app.state.limiter is rate_limit.limiter

    assert [
        call.args[0]
        for call in app.add_middleware.call_args_list
    ] == [
        rate_limit.SlowAPIMiddleware,
        rate_limit.MaintenanceModeMiddleware,
        rate_limit.SafeSlowAPIMiddleware,
    ]

    log_info.assert_called_once_with(
        "Rate limiter enabled "
        "(ENV=%s, storage=%s).",
        "prod",
        "redis://redis.example",
    )