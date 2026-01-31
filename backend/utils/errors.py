'''
Global exception handling utilities for FastAPI.

Registers consistent JSON error responses for:
- Request validation errors (422)
- HTTP exceptions raised by routes/middleware
'''

import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
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
        safe_errors = jsonable_encoder(exc.errors())
        logger.info("validation error: %s", safe_errors)
        return JSONResponse(status_code=422, content=error("Validation error", detail=safe_errors))

    @app.exception_handler(HTTPException)
    async def _http(_req: Request, exc: HTTPException):
        # Only retrn the stack trace for errors that are 5xx coded.
        if exc.status_code >= 500:
            logger.error("http error %s: %s", exc.status_code, exc.detail, exc_info=True)
        else:
            logger.info("http error %s: %s", exc.status_code, exc.detail)
        return JSONResponse(status_code=exc.status_code, content=error("Error", detail=exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception):
        logger.error(f"unhandled: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content=error("Internal server error", detail="An unexpected error occurred"))
