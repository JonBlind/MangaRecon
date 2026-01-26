'''
SlowAPI rate limiting integration and setup.

Exposes:
- `limiter`: shared Limiter instance (keyed by remote address)
- `register_rate_limiter(app)`: attach middleware + error handler
'''

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
from backend.utils.response import error

ENV = os.getenv("MANGARECON_ENV", "dev").lower()

if ENV == "test":
    storage_uri = "memory://"
else:
    storage_uri = os.getenv("RATELIMIT_STORAGE_URI") 

limiter = Limiter(
    key_func = get_remote_address,
    default_limits = ["60/minute"],
    storage_uri = storage_uri,
)

# For testing purposes, disable rate-limiter because we know it works.
if ENV == "test":
    limiter.enabled = False

def register_rate_limiter(app):
    '''
    Attach SlowAPI rate limiting to the application and its error handler.

    Args:
        app (FastAPI): The FastAPI application instance.

    Returns:
        None: Middleware and exception handler are registered on the app.
    '''
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error("Too many requests! Rate Limit Exceeded!", detail=str(exc))
        )