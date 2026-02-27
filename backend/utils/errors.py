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
from slowapi.errors import RateLimitExceeded
from backend.utils.response import error
from backend.utils.domain_exceptions import DomainError

logger = logging.getLogger(__name__)

HTTP_DETAIL_MAP: dict[str, tuple[int, str, str]] = {
    # detail_string: (status_code, code, message)
    "LOGIN_BAD_CREDENTIALS": (401, "AUTH_INVALID_CREDENTIALS", "Invalid Email or Password."),
    "LOGIN_USER_NOT_VERIFIED": (403, "AUTH_NOT_VERIFIED", "Please verify your email before logging in."),
    "REGISTER_USER_ALREADY_EXISTS": (409, "AUTH_EMAIL_EXISTS", "An account with that email already exists."),
}

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

    @app.exception_handler(DomainError)
    async def _domain(_req: Request, exc: DomainError):
        logger.info("domain error %s: %s", exc.status_code, exc.code)

        data = {"detail": exc.detail} if exc.detail is not None else None
        return JSONResponse(status_code=exc.status_code, content=error(exc.message, detail=exc.code, data=data))

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit(_req: Request, _exc: RateLimitExceeded):
        logger.info("rate limit exceeded")
        return JSONResponse(status_code=429, content=error("Rate limit exceeded", detail="RATE_LIMIT_EXCEEDED"))

    @app.exception_handler(HTTPException)
    async def _http(_req: Request, exc: HTTPException):
        if isinstance(exc.detail, str) and exc.detail in HTTP_DETAIL_MAP:
            status_code, code, message = HTTP_DETAIL_MAP[exc.detail]
            logger.info("http mapped %s -> %s", exc.detail, code)
            return JSONResponse(status_code=status_code, content=error(message, detail=code))

        # Unmapped HTTPExceptions are treated as infrastructure errors
        if exc.status_code >= 500:
            logger.error("http error %s: %s", exc.status_code, exc.detail, exc_info=True)
        else:
            logger.info("http error %s: %s", exc.status_code, exc.detail)

        if isinstance(exc.detail, str):
            return JSONResponse(status_code=exc.status_code, content=error(exc.detail, detail="HTTP_EXCEPTION"))
        
        return JSONResponse(status_code=exc.status_code, content=error("Request failed.", detail="HTTP_EXCEPTION"))

    @app.exception_handler(Exception)
    async def _unexpected(_req: Request, exc: Exception):
        logger.error("unhandled: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content=error("Internal server error", detail="INTERNAL_SERVER_ERROR"))
    
    