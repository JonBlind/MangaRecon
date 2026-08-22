from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config.settings import settings
from backend.utils.response import error


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """Return a deliberate 503 while operator-controlled maintenance is active."""

    async def dispatch(self, request: Request, call_next):
        if not settings.maintenance_mode or request.url.path == "/healthz":
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content=error(
                "Service unavailable",
                detail="MAINTENANCE_MODE",
            ),
            headers={
                "Retry-After": str(settings.maintenance_retry_after_seconds),
                "Cache-Control": "no-store",
            },
        )
