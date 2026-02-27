import os
import logging
from urllib.parse import urlparse

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from backend.utils.response import error
from redis.asyncio import Redis
import time

logger = logging.getLogger(__name__)

ENV = os.getenv("MANGARECON_ENV", "prod").lower()


def _get_storage_uri() -> str:
    if ENV in ("dev", "test"):
        return "memory://"

    uri = os.getenv("RATELIMIT_STORAGE_URI")
    if not uri:
        raise RuntimeError("RATELIMIT_STORAGE_URI must be set when MANGARECON_ENV=prod.")
    return uri

async def rate_limit_storage_ready(timeout: float = 0.25) -> bool:
    if ENV in ("dev", "test"):
        return True

    uri = os.getenv("RATELIMIT_STORAGE_URI")
    if not uri:
        return False

    scheme = urlparse(uri).scheme.lower()
    if scheme not in ("redis", "rediss"):
        return True

    client = None
    try:
        client = Redis.from_url(uri, decode_responses=True, socket_connect_timeout=timeout, socket_timeout=timeout)
        return bool(await client.ping())
    
    except Exception:
        return False
    
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if ENV in ("dev", "test"):
            return await call_next(request)

        ready = getattr(request.app.state, "rate_limit_storage_ready", False)

        if not ready:
            now = time.monotonic()
            last = getattr(request.app.state, "rate_limit_last_check", 0.0)
            interval = getattr(request.app.state, "rate_limit_check_interval", 15.0)

            if now - last >= interval:
                request.app.state.rate_limit_last_check = now
                ok = await rate_limit_storage_ready()
                request.app.state.rate_limit_storage_ready = ok
                ready = ok

        if ready:
            return await call_next(request)

        if request.url.path == "/healthz":
            return await call_next(request)

        return JSONResponse(status_code=503, content=error("Service unavailable", detail="TEMPORARILY_UNAVAILABLE"))
    
class SafeSlowAPIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except RateLimitExceeded:
            return JSONResponse(status_code=429, content=error("Rate limit exceeded", detail="RATE_LIMIT_EXCEEDED"))

        except Exception as e:
            if self._has_detail_attribute_error(e):
                self._log_slowapi_crash(request)
                return JSONResponse(status_code=503, content=error("Service unavailable", detail="RATE_LIMIT_UNAVAILABLE"))

            if self._has_connection_error(e):
                self._log_limiter_down(request)
                return JSONResponse(status_code=503, content=error("Service unavailable", detail="RATE_LIMIT_UNAVAILABLE"))
            
    def _has_detail_attribute_error(self, exc: BaseException) -> bool:
        for sub in self._iter_exceptions(exc):
            if isinstance(sub, AttributeError) and "has no attribute 'detail'" in str(sub):
                return True
        return False

    def _has_connection_error(self, exc: BaseException) -> bool:
        for sub in self._iter_exceptions(exc):
            if sub.__class__.__name__ == "ConnectionError":
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
        last = getattr(request.app.state, "rate_limit_last_log", 0.0)
        interval = getattr(request.app.state, "rate_limit_check_interval", 15.0)

        if now - last < interval:
            return

        request.app.state.rate_limit_last_log = now
        logger.warning("Rate limit storage connection failed (Redis unreachable).")

    def _log_slowapi_crash(self, request: Request) -> None:
        now = time.monotonic()
        last = getattr(request.app.state, "rate_limit_last_log", 0.0)
        interval = getattr(request.app.state, "rate_limit_check_interval", 15.0)

        if now - last < interval:
            return

        request.app.state.rate_limit_last_log = now
        logger.warning("SlowAPI rate limiter error handler crashed; returning 503.")


_storage_uri = _get_storage_uri()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    storage_uri=_storage_uri,
)

if ENV in ("dev", "test"):
    limiter.enabled = False


def register_rate_limiter(app) -> None:
    app.state.limiter = limiter

    if ENV in ("dev", "test"):
        logger.info("Rate limiter disabled (ENV=%s).", ENV)
        return

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(MaintenanceModeMiddleware)
    app.add_middleware(SafeSlowAPIMiddleware)
    logger.info("Rate limiter enabled (ENV=%s, storage=%s).", ENV, _storage_uri)