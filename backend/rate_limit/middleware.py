import hashlib
import ipaddress
import logging
import re
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from backend.rate_limit.account import (
    AccountRateLimitStorageError,
    account_rate_limiter,
)
from backend.cache.redis import get_redis_url
from backend.config.settings import ENV, settings as app_settings
from backend.utils.response import error

logger = logging.getLogger(__name__)

_ACCOUNT_EMAIL_REQUEST_PATHS = frozenset(
    {
        "/auth/register",
        "/auth/forgot-password",
        "/auth/request-verify-token",
    }
)
_ACCOUNT_TOKEN_REQUESTS = frozenset(
    {
        ("GET", "/auth/reset-password"),
        ("POST", "/auth/reset-password"),
        ("POST", "/auth/verify"),
    }
)

_HEADER_NAME_PATTERN = re.compile(
    r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$"
)


class RateLimitIdentityUnavailable(RuntimeError):
    pass


def _secret_setting(name: str) -> str:
    configured = getattr(app_settings, name)
    if configured is None:
        return ""
    return configured.get_secret_value()


def _origin_verify_header_name() -> str:
    return _secret_setting("origin_verify_header_name")


def _origin_verify_secret_digest() -> str:
    return _secret_setting("origin_verify_secret_digest")


def _trusted_client_address_header_name() -> str:
    return _secret_setting("trusted_client_address_header_name")


def _is_valid_secret_digest(value: str) -> bool:
    if len(value) != hashlib.sha256().digest_size * 2:
        return False

    try:
        bytes.fromhex(value)
    except ValueError:
        return False

    return value == value.lower()


def _origin_is_verified(request: Request) -> bool:
    header_name = _origin_verify_header_name()
    expected_digest = _origin_verify_secret_digest()

    if not header_name or not expected_digest:
        return False

    supplied = request.headers.get(header_name, "")
    if not supplied:
        return False

    supplied_digest = hashlib.sha256(
        supplied.encode("utf-8")
    ).hexdigest()

    return secrets.compare_digest(
        supplied_digest,
        expected_digest,
    )


def _parse_client_address(value: str | None) -> str | None:
    if not value:
        return None

    address = value.strip()
    if not address or "," in address or "%" in address:
        return None

    # Cloudflare's CF-Connecting-IP contains one bare IPv4 or IPv6 address.
    try:
        return ipaddress.ip_address(address).compressed
    except ValueError:
        pass

    # Also accept the socket-address form used by some hosting proxies.
    if address.startswith("["):
        closing_bracket = address.find("]")
        separator = address[
            closing_bracket + 1 : closing_bracket + 2
        ]
        if closing_bracket < 0 or separator != ":":
            return None
        host = address[1:closing_bracket]
        port_text = address[closing_bracket + 2 :]
    else:
        host, separator, port_text = address.rpartition(":")
        if not separator:
            return None

    try:
        port = int(port_text)
        if not 1 <= port <= 65535:
            return None
        return ipaddress.ip_address(host).compressed
    except (TypeError, ValueError):
        return None


def get_rate_limit_key(request: Request) -> str:
    if ENV != "prod":
        return get_remote_address(request)

    client_ip = getattr(
        request.state,
        "rate_limit_client_ip",
        None,
    )

    if client_ip is None:
        raise RateLimitIdentityUnavailable

    return client_ip


def _get_storage_uri() -> str:
    if ENV in ("dev", "test"):
        return "memory://"

    return get_redis_url(required=True)


def _get_storage_options() -> dict:
    """Bound Redis waits and connections used by SlowAPI's storage client."""
    if ENV in ("dev", "test"):
        return {}

    return {
        "socket_connect_timeout": (
            app_settings.redis_connect_timeout_seconds
        ),
        "socket_timeout": app_settings.redis_operation_timeout_seconds,
        "max_connections": app_settings.redis_max_connections,
    }


def validate_rate_limit_config() -> None:
    """Validate production rate-limit configuration."""
    if ENV in ("dev", "test"):
        return

    get_redis_url(required=True)

    origin_header_name = _origin_verify_header_name()
    client_header_name = (
        _trusted_client_address_header_name()
    )
    secret_digest = _origin_verify_secret_digest()

    if (
        not _HEADER_NAME_PATTERN.fullmatch(
            origin_header_name
        )
        or not _HEADER_NAME_PATTERN.fullmatch(
            client_header_name
        )
        or origin_header_name.casefold()
        == client_header_name.casefold()
        or not _is_valid_secret_digest(
            secret_digest
        )
    ):
        raise RuntimeError(
            "Production origin verification "
            "configuration is invalid."
        )


async def rate_limit_storage_ready(
    timeout: float | None = None,
) -> bool:
    if ENV in ("dev", "test"):
        return True

    resolved_timeout = (
        app_settings.redis_ready_timeout_seconds
        if timeout is None
        else timeout
    )

    try:
        uri = get_redis_url(required=True)
    except RuntimeError:
        return False

    client = None
    try:
        client = Redis.from_url(
            uri,
            decode_responses=True,
            socket_connect_timeout=resolved_timeout,
            socket_timeout=resolved_timeout,
            max_connections=app_settings.redis_max_connections,
        )
        return bool(await client.ping())

    except Exception:
        return False

    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass


class RateLimitStorageGuardMiddleware(BaseHTTPMiddleware):
    """Fail closed when production rate-limit storage is unavailable."""

    async def dispatch(self, request: Request, call_next):
        if ENV in ("dev", "test"):
            return await call_next(request)

        if request.url.path == "/healthz":
            return JSONResponse(
                status_code=200,
                content={
                    "message": "MangaRecon API is running."
                },
            )

        if request.url.path == "/readyz":
            return await call_next(request)

        ready = getattr(
            request.app.state,
            "rate_limit_storage_ready",
            False,
        )

        if not ready:
            now = time.monotonic()
            last = getattr(
                request.app.state,
                "rate_limit_last_check",
                0.0,
            )
            interval = getattr(
                request.app.state,
                "rate_limit_check_interval",
                15.0,
            )

            if now - last >= interval:
                request.app.state.rate_limit_last_check = now
                ok = await rate_limit_storage_ready()
                request.app.state.rate_limit_storage_ready = ok
                ready = ok

        if ready:
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content=error(
                "Service unavailable",
                detail="TEMPORARILY_UNAVAILABLE",
            ),
            headers={"Retry-After": "15"},
        )


class TrustedOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if ENV != "prod" or request.url.path == "/healthz":
            return await call_next(request)

        if not _origin_is_verified(request):
            return JSONResponse(
                status_code=403,
                content=error("Forbidden", detail="FORBIDDEN"),
            )

        client_ip = _parse_client_address(
            request.headers.get(
                _trusted_client_address_header_name()
            )
        )
        if client_ip is None:
            return JSONResponse(
                status_code=503,
                content=error(
                    "Service unavailable",
                    detail="TEMPORARILY_UNAVAILABLE",
                ),
            )

        request.state.rate_limit_client_ip = client_ip
        return await call_next(request)


class AccountAuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply stricter IP limits to account-email and token endpoints."""

    async def dispatch(self, request: Request, call_next):
        if ENV != "prod":
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path

        check_limit = None
        if method == "POST" and path in _ACCOUNT_EMAIL_REQUEST_PATHS:
            check_limit = account_rate_limiter.check_email_ip
        elif (method, path) in _ACCOUNT_TOKEN_REQUESTS:
            check_limit = account_rate_limiter.check_token_ip

        if check_limit is None:
            return await call_next(request)

        decision = await check_limit(get_rate_limit_key(request))
        if decision.allowed:
            return await call_next(request)

        retry_after = max(1, decision.retry_after or 1)
        return JSONResponse(
            status_code=429,
            content=error(
                "Rate limit exceeded",
                detail="RATE_LIMIT_EXCEEDED",
            ),
            headers={"Retry-After": str(retry_after)},
        )


class SafeSlowAPIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except RateLimitExceeded:
            return JSONResponse(
                status_code=429,
                content=error(
                    "Rate limit exceeded",
                    detail="RATE_LIMIT_EXCEEDED",
                ),
            )

        except RateLimitIdentityUnavailable:
            return JSONResponse(
                status_code=503,
                content=error(
                    "Service unavailable",
                    detail="TEMPORARILY_UNAVAILABLE",
                ),
            )

        except Exception as e:
            if self._has_detail_attribute_error(e):
                self._log_slowapi_crash(request)
                return JSONResponse(
                    status_code=503,
                    content=error(
                        "Service unavailable",
                        detail="TEMPORARILY_UNAVAILABLE",
                    ),
                )

            if self._has_connection_error(e):
                self._log_limiter_down(request)
                return JSONResponse(
                    status_code=503,
                    content=error(
                        "Service unavailable",
                        detail="TEMPORARILY_UNAVAILABLE",
                    ),
                )
            raise

    def _has_detail_attribute_error(self, exc: BaseException) -> bool:
        for sub in self._iter_exceptions(exc):
            if (
                isinstance(sub, AttributeError)
                and "has no attribute 'detail'" in str(sub)
            ):
                return True
        return False

    def _has_connection_error(self, exc: BaseException) -> bool:
        for sub in self._iter_exceptions(exc):
            if (
                isinstance(sub, AccountRateLimitStorageError)
                or sub.__class__.__name__ == "ConnectionError"
            ):
                return True
        return False

    def _iter_exceptions(self, exc: BaseException):
        yield exc
        group = getattr(exc, "exceptions", None)
        if not group:
            return
        for sub in group:
            yield sub
            nested = getattr(sub, "exceptions", None)
            if nested:
                for x in self._iter_exceptions(sub):
                    yield x

    def _log_limiter_down(self, request: Request) -> None:
        now = time.monotonic()
        last = getattr(
            request.app.state,
            "rate_limit_last_log",
            0.0,
        )
        interval = getattr(
            request.app.state,
            "rate_limit_check_interval",
            15.0,
        )

        if now - last < interval:
            return

        request.app.state.rate_limit_last_log = now
        logger.warning(
            "Rate limit storage connection failed "
            "(Redis unreachable)."
        )

    def _log_slowapi_crash(self, request: Request) -> None:
        now = time.monotonic()
        last = getattr(
            request.app.state,
            "rate_limit_last_log",
            0.0,
        )
        interval = getattr(
            request.app.state,
            "rate_limit_check_interval",
            15.0,
        )

        if now - last < interval:
            return

        request.app.state.rate_limit_last_log = now
        logger.warning(
            "SlowAPI rate limiter error handler crashed; "
            "returning 503."
        )


_storage_uri = _get_storage_uri()

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=["60/minute"],
    storage_uri=_storage_uri,
    storage_options=_get_storage_options(),
)

if ENV in ("dev", "test"):
    limiter.enabled = False


def register_rate_limiter(app) -> None:
    app.state.limiter = limiter

    if ENV in ("dev", "test"):
        logger.info("Rate limiter disabled (ENV=%s).", ENV)
        return

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(AccountAuthRateLimitMiddleware)
    app.add_middleware(RateLimitStorageGuardMiddleware)
    app.add_middleware(SafeSlowAPIMiddleware)
    app.add_middleware(TrustedOriginMiddleware)
    logger.info("Rate limiter enabled (ENV=%s, storage=Redis).", ENV)
