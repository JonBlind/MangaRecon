import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from backend.rate_limit.account import AccountRateLimitDecision
from backend.rate_limit import middleware as rate_limit


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


def make_request(
    path="/mangas",
    *,
    method="GET",
    headers=None,
    client_host="127.0.0.1",
    rate_limit_client_ip=None,
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

    request = SimpleNamespace(
        url=SimpleNamespace(path=path),
        method=method,
        app=app,
        headers=headers or {},
        client=SimpleNamespace(host=client_host),
        state=SimpleNamespace(),
    )

    if rate_limit_client_ip is not None:
        request.state.rate_limit_client_ip = rate_limit_client_ip

    return request


def make_middleware(middleware_class):
    return middleware_class(MagicMock())


def configure_origin_settings(
    monkeypatch,
    *,
    origin_header="X-Test-Origin",
    secret="test-origin-secret",
    secret_digest=None,
    client_header="X-Test-Client-Address",
):
    if secret_digest is None and secret is not None:
        secret_digest = hashlib.sha256(
            secret.encode("utf-8")
        ).hexdigest()

    monkeypatch.setattr(
        rate_limit.app_settings,
        "origin_verify_header_name",
        (
            SecretStr(origin_header)
            if origin_header is not None
            else None
        ),
    )
    monkeypatch.setattr(
        rate_limit.app_settings,
        "origin_verify_secret_digest",
        (
            SecretStr(secret_digest)
            if secret_digest is not None
            else None
        ),
    )
    monkeypatch.setattr(
        rate_limit.app_settings,
        "trusted_client_address_header_name",
        (
            SecretStr(client_header)
            if client_header is not None
            else None
        ),
    )


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
        "REDIS_URL",
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
        "REDIS_URL",
        "rediss://user:secret@redis.example:6380/1",
    )

    assert rate_limit._get_storage_uri() == (
        "rediss://user:secret@redis.example:6380/1"
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
        "REDIS_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "REDIS_URL must be set "
            "when MANGARECON_ENV=prod"
        ),
    ):
        rate_limit._get_storage_uri()


@pytest.mark.parametrize(
    "environment",
    ["dev", "test"],
)
def test_storage_options_are_empty_outside_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )

    assert rate_limit._get_storage_options() == {}


def test_storage_options_bound_production_redis_client(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    monkeypatch.setattr(
        rate_limit.app_settings,
        "redis_connect_timeout_seconds",
        2.5,
    )
    monkeypatch.setattr(
        rate_limit.app_settings,
        "redis_operation_timeout_seconds",
        3.5,
    )
    monkeypatch.setattr(
        rate_limit.app_settings,
        "redis_max_connections",
        6,
    )

    assert rate_limit._get_storage_options() == {
        "socket_connect_timeout": 2.5,
        "socket_timeout": 3.5,
        "max_connections": 6,
    }


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
        "REDIS_URL",
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
        "REDIS_URL",
        "rediss://redis.example:6380/0",
    )
    configure_origin_settings(monkeypatch)

    assert rate_limit.validate_rate_limit_config() is None


@pytest.mark.parametrize(
    "configured",
    [
        None,
        "invalid",
        "g" * 64,
        "F" * 64,
        "f" * 63,
        "f" * 65,
    ],
)
def test_validate_rate_limit_config_rejects_invalid_origin_digest(
    monkeypatch,
    configured,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    monkeypatch.setenv(
        "REDIS_URL",
        "rediss://redis.example:6380/0",
    )
    configure_origin_settings(
        monkeypatch,
        secret=None,
        secret_digest=configured,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Production origin verification "
            "configuration is invalid"
        ),
    ):
        rate_limit.validate_rate_limit_config()


@pytest.mark.parametrize(
    ("origin_header", "client_header"),
    [
        (None, "X-Test-Client-Address"),
        ("invalid header", "X-Test-Client-Address"),
        ("X-Test-Origin", None),
        ("X-Test-Origin", "invalid header"),
        ("X-Test-Origin", "x-test-origin"),
    ],
)
def test_validate_rate_limit_config_rejects_invalid_header_settings(
    monkeypatch,
    origin_header,
    client_header,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    monkeypatch.setenv(
        "REDIS_URL",
        "rediss://redis.example:6380/0",
    )
    configure_origin_settings(
        monkeypatch,
        origin_header=origin_header,
        client_header=client_header,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Production origin verification "
            "configuration is invalid"
        ),
    ):
        rate_limit.validate_rate_limit_config()


def test_validate_rate_limit_config_rejects_missing_production_uri(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.delenv(
        "REDIS_URL",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "REDIS_URL must be set when "
            "MANGARECON_ENV=prod"
        ),
    ):
        rate_limit.validate_rate_limit_config()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("198.51.100.10", "198.51.100.10"),
        ("2001:db8::1", "2001:db8::1"),
        ("198.51.100.10:46532", "198.51.100.10"),
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("2001:db8::1:443", "2001:db8::1:443"),
        (None, None),
        ("", None),
        ("198.51.100.10, 203.0.113.7", None),
        ("fe80::1%eth0", None),
        ("198.51.100.10:0", None),
        ("198.51.100.10:65536", None),
        ("198.51.100.10:not-a-port", None),
        ("not-an-ip:443", None),
        ("[2001:db8::1]443", None),
    ],
)
def test_parse_client_address(
    value,
    expected,
):
    assert (
        rate_limit._parse_client_address(value)
        == expected
    )


def test_rate_limit_key_uses_remote_address_outside_production(
    monkeypatch,
):
    remote_address = MagicMock(
        return_value="203.0.113.20"
    )
    request = make_request()

    monkeypatch.setattr(rate_limit, "ENV", "dev")
    monkeypatch.setattr(
        rate_limit,
        "get_remote_address",
        remote_address,
    )

    assert rate_limit.get_rate_limit_key(request) == (
        "203.0.113.20"
    )
    remote_address.assert_called_once_with(request)


def test_limiter_uses_proxy_aware_key_function():
    assert rate_limit.limiter._key_func is (
        rate_limit.get_rate_limit_key
    )


def test_rate_limit_key_uses_validated_client_identity(
    monkeypatch,
):
    request = make_request()
    request.state.rate_limit_client_ip = "198.51.100.10"

    monkeypatch.setattr(rate_limit, "ENV", "prod")

    assert rate_limit.get_rate_limit_key(request) == (
        "198.51.100.10"
    )


def test_rate_limit_key_fails_closed_without_validated_identity(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")

    with pytest.raises(
        rate_limit.RateLimitIdentityUnavailable
    ):
        rate_limit.get_rate_limit_key(make_request())


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["dev", "test"])
async def test_trusted_origin_middleware_is_disabled_outside_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(rate_limit, "ENV", environment)
    middleware = make_middleware(
        rate_limit.TrustedOriginMiddleware
    )
    request = make_request()
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_trusted_origin_middleware_allows_health_probe(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    middleware = make_middleware(
        rate_limit.TrustedOriginMiddleware
    )
    request = make_request(path="/healthz")
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_trusted_origin_middleware_rejects_unverified_origin(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    configure_origin_settings(monkeypatch)
    middleware = make_middleware(
        rate_limit.TrustedOriginMiddleware
    )
    request = make_request(
        headers={"X-Test-Origin": "wrong"}
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 403
    assert response_json(response)["detail"] == "FORBIDDEN"
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_trusted_origin_middleware_requires_viewer_address(
    monkeypatch,
):
    secret = "test-origin-secret"
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    configure_origin_settings(
        monkeypatch,
        secret=secret,
    )
    middleware = make_middleware(
        rate_limit.TrustedOriginMiddleware
    )
    request = make_request(
        headers={"X-Test-Origin": secret}
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 503
    assert response_json(response)["detail"] == (
        "TEMPORARILY_UNAVAILABLE"
    )
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_trusted_origin_middleware_sets_client_ip(
    monkeypatch,
):
    secret = "test-origin-secret"
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    configure_origin_settings(
        monkeypatch,
        secret=secret,
    )
    middleware = make_middleware(
        rate_limit.TrustedOriginMiddleware
    )
    request = make_request(
        headers={
            "X-Test-Origin": secret,
            "X-Test-Client-Address": "2001:db8::1",
        }
    )
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    assert request.state.rate_limit_client_ip == "2001:db8::1"
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["dev", "test"])
async def test_account_auth_limiter_is_disabled_outside_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(rate_limit, "ENV", environment)
    check_email_ip = AsyncMock()
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_email_ip",
        check_email_ip,
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        "/auth/forgot-password",
        method="POST",
    )
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    check_email_ip.assert_not_awaited()
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_account_auth_limiter_ignores_unrelated_route(monkeypatch):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    check_email_ip = AsyncMock()
    check_token_ip = AsyncMock()
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_email_ip",
        check_email_ip,
    )
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_token_ip",
        check_token_ip,
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        "/auth/jwt/login",
        method="POST",
        rate_limit_client_ip="198.51.100.23",
    )
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    check_email_ip.assert_not_awaited()
    check_token_ip.assert_not_awaited()
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/auth/register",
        "/auth/forgot-password",
        "/auth/request-verify-token",
    ],
)
async def test_account_email_routes_use_strict_ip_limit(
    monkeypatch,
    path,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    check_email_ip = AsyncMock(
        return_value=AccountRateLimitDecision(allowed=True)
    )
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_email_ip",
        check_email_ip,
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        path,
        method="POST",
        rate_limit_client_ip="198.51.100.23",
    )
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    check_email_ip.assert_awaited_once_with("198.51.100.23")
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/auth/reset-password"),
        ("POST", "/auth/reset-password"),
        ("POST", "/auth/verify"),
    ],
)
async def test_account_token_routes_use_strict_ip_limit(
    monkeypatch,
    method,
    path,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    check_token_ip = AsyncMock(
        return_value=AccountRateLimitDecision(allowed=True)
    )
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_token_ip",
        check_token_ip,
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        path,
        method=method,
        rate_limit_client_ip="2001:db8::1",
    )
    expected = MagicMock()
    call_next = AsyncMock(return_value=expected)

    result = await middleware.dispatch(request, call_next)

    assert result is expected
    check_token_ip.assert_awaited_once_with("2001:db8::1")
    call_next.assert_awaited_once_with(request)


@pytest.mark.asyncio
async def test_account_auth_limiter_returns_429_with_retry_after(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    check_email_ip = AsyncMock(
        return_value=AccountRateLimitDecision(
            allowed=False,
            retry_after=37,
        )
    )
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_email_ip",
        check_email_ip,
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        "/auth/forgot-password",
        method="POST",
        rate_limit_client_ip="198.51.100.23",
    )
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "37"
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Rate limit exceeded",
        "detail": "RATE_LIMIT_EXCEEDED",
    }
    call_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_account_auth_limiter_propagates_storage_failure(
    monkeypatch,
):
    monkeypatch.setattr(rate_limit, "ENV", "prod")
    storage_error = rate_limit.AccountRateLimitStorageError(
        "storage unavailable"
    )
    monkeypatch.setattr(
        rate_limit.account_rate_limiter,
        "check_email_ip",
        AsyncMock(side_effect=storage_error),
    )
    middleware = make_middleware(
        rate_limit.AccountAuthRateLimitMiddleware
    )
    request = make_request(
        "/auth/register",
        method="POST",
        rate_limit_client_ip="198.51.100.23",
    )

    with pytest.raises(rate_limit.AccountRateLimitStorageError):
        await middleware.dispatch(request, AsyncMock())


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
        "REDIS_URL",
        raising=False,
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False


@pytest.mark.asyncio
async def test_storage_ready_rejects_non_redis_url_without_ping(
    monkeypatch,
):
    from_url = MagicMock()

    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )
    monkeypatch.setenv(
        "REDIS_URL",
        "https://redis.example",
    )
    monkeypatch.setattr(
        rate_limit.Redis,
        "from_url",
        from_url,
    )

    result = await rate_limit.rate_limit_storage_ready()

    assert result is False
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
        "REDIS_URL",
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
        max_connections=(
            rate_limit.app_settings.redis_max_connections
        ),
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
        "REDIS_URL",
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
        "REDIS_URL",
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
        "REDIS_URL",
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
        "REDIS_URL",
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
async def test_storage_guard_bypasses_checks_in_non_production(
    monkeypatch,
    environment,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        environment,
    )

    middleware = make_middleware(
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_storage_guard_health_endpoint_always_returns_200(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_storage_guard_allows_ready_probe_to_reach_route(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.RateLimitStorageGuardMiddleware
    )
    request = make_request(
        "/readyz",
        ready=False,
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
async def test_storage_guard_allows_normal_request_when_ready(
    monkeypatch,
):
    monkeypatch.setattr(
        rate_limit,
        "ENV",
        "prod",
    )

    middleware = make_middleware(
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_storage_guard_blocks_normal_request_when_unready(
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
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_storage_guard_rechecks_storage_after_interval_and_recovers(
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
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_storage_guard_rechecks_storage_and_remains_unready(
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
        rate_limit.RateLimitStorageGuardMiddleware
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
async def test_safe_middleware_converts_missing_identity_to_503():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    response = await middleware.dispatch(
        make_request(),
        AsyncMock(
            side_effect=(
                rate_limit.RateLimitIdentityUnavailable()
            )
        ),
    )

    assert response.status_code == 503
    assert response_json(response)["detail"] == (
        "TEMPORARILY_UNAVAILABLE"
    )


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
        "TEMPORARILY_UNAVAILABLE"
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
        "TEMPORARILY_UNAVAILABLE"
    )
    log_down.assert_called_once_with(request)


@pytest.mark.asyncio
async def test_safe_middleware_converts_account_storage_error_to_503(
    monkeypatch,
):
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
            side_effect=rate_limit.AccountRateLimitStorageError(
                "Redis unavailable"
            )
        ),
    )

    assert response.status_code == 503
    assert response_json(response)["detail"] == (
        "TEMPORARILY_UNAVAILABLE"
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


def test_has_connection_error_detects_account_limiter_storage_error():
    middleware = make_middleware(
        rate_limit.SafeSlowAPIMiddleware
    )

    assert middleware._has_connection_error(
        rate_limit.AccountRateLimitStorageError("down")
    ) is True


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
        "rediss://user:secret@redis.example:6380/0",
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
        rate_limit.AccountAuthRateLimitMiddleware,
        rate_limit.RateLimitStorageGuardMiddleware,
        rate_limit.SafeSlowAPIMiddleware,
        rate_limit.TrustedOriginMiddleware,
    ]

    log_info.assert_called_once_with(
        "Rate limiter enabled "
        "(ENV=%s, storage=Redis).",
        "prod",
    )

    logged_arguments = repr(log_info.call_args)
    assert "user" not in logged_arguments
    assert "secret" not in logged_arguments
    assert "redis.example" not in logged_arguments
