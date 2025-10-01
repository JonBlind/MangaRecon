'''
Global exception handling utilities for FastAPI.

Registers consistent JSON error responses for:
- Request validation errors (422)
- HTTP exceptions raised by routes/middleware
'''

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.utils.response import error

logger = logging.getLogger(__name__)

def register_exception_handlers(app):
    '''
   Register global exception handlers on the FastAPI app.

    Installs handlers for request validation errors and HTTP exceptions to
    ensure consistent JSON error envelopes and logging behavior.

    Args:
        app (FastAPI): The FastAPI application instance.

    Returns:
        None: Handlers are registered via FastAPI decorators.
   '''
   
    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError):
        logger.warning(f"validation error: {exc}")
        return JSONResponse(status_code=422, content=error("Validation error", detail=exc.errors()))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException):
        logger.warning(f"http error: {exc.detail}")
        return JSONResponse(status_code=exc.status_code, content=error("Error", detail=exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception):
        logger.error(f"unhandled: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content=error("Internal server error", detail="An unexpected error occurred"))
