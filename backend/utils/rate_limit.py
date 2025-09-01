import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.utils.response import error

limiter = Limiter(
    key_func = get_remote_address,
    default_limits = ["60/minute"],
    storage_uri = os.getenv("RATELIMIT_STORAGE_URI"),
)

def register_rate_limiter(app):
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error("Too many requests", detail=str(exc))
        )