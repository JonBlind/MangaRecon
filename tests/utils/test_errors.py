from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded

from backend.utils import errors
from backend.utils.domain_exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def exception_handler(self, exception_type):
        def decorator(handler):
            self.handlers[exception_type] = handler
            return handler

        return decorator


@pytest.fixture
def registered_handlers():
    app = FakeApp()

    result = errors.register_exception_handlers(app)

    assert result is None

    return app.handlers


def response_json(response):
    import json

    return json.loads(response.body.decode("utf-8"))


def test_register_exception_handlers_registers_all_handlers(
    registered_handlers,
):
    assert RequestValidationError in registered_handlers
    assert errors.DomainError in registered_handlers
    assert RateLimitExceeded in registered_handlers
    assert HTTPException in registered_handlers
    assert Exception in registered_handlers


@pytest.mark.asyncio
async def test_validation_handler_returns_standard_422_response(
    monkeypatch,
    registered_handlers,
):
    safe_errors = [
        {
            "type": "missing",
            "loc": ["body", "email"],
            "msg": "Field required",
            "input": {},
        }
    ]

    validation_exception = MagicMock(
        spec=RequestValidationError
    )
    validation_exception.errors.return_value = safe_errors

    encoder = MagicMock(
        return_value=safe_errors
    )
    log_info = MagicMock()

    monkeypatch.setattr(
        errors,
        "jsonable_encoder",
        encoder,
    )
    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    handler = registered_handlers[
        RequestValidationError
    ]

    response = await handler(
        MagicMock(),
        validation_exception,
    )

    assert response.status_code == 422
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Validation error",
        "detail": safe_errors,
    }

    validation_exception.errors.assert_called_once_with()
    encoder.assert_called_once_with(safe_errors)

    log_info.assert_called_once_with(
        "validation error: %s",
        safe_errors,
    )


@pytest.mark.asyncio
async def test_domain_handler_returns_error_without_detail_data(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    exception = NotFoundError(
        code="MANGA_NOT_FOUND",
        message="Manga not found.",
    )

    handler = registered_handlers[
        errors.DomainError
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 404
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Manga not found.",
        "detail": "MANGA_NOT_FOUND",
    }

    log_info.assert_called_once_with(
        "domain error %s: %s",
        404,
        "MANGA_NOT_FOUND",
    )


@pytest.mark.asyncio
async def test_domain_handler_includes_structured_detail_data(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    detail = {
        "collection_id": 10,
        "manga_id": 25,
    }

    exception = ConflictError(
        code="COLLECTION_MANGA_CONFLICT",
        message="Manga is already in this collection.",
        detail=detail,
    )

    handler = registered_handlers[
        errors.DomainError
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 409
    assert response_json(response) == {
        "status": "error",
        "data": {
            "detail": detail,
        },
        "message": (
            "Manga is already in this collection."
        ),
        "detail": "COLLECTION_MANGA_CONFLICT",
    }


@pytest.mark.asyncio
async def test_domain_handler_supports_bad_request_error(
    registered_handlers,
):
    exception = BadRequestError(
        code="INVALID_INPUT",
        message="Input was invalid.",
    )

    handler = registered_handlers[
        errors.DomainError
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 400
    assert response_json(response)["message"] == (
        "Input was invalid."
    )
    assert response_json(response)["detail"] == (
        "INVALID_INPUT"
    )


@pytest.mark.asyncio
async def test_rate_limit_handler_returns_standard_429_response(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    handler = registered_handlers[
        RateLimitExceeded
    ]

    response = await handler(
        MagicMock(),
        MagicMock(),
    )

    assert response.status_code == 429
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Rate limit exceeded",
        "detail": "RATE_LIMIT_EXCEEDED",
    }

    log_info.assert_called_once_with(
        "rate limit exceeded"
    )


@pytest.mark.parametrize(
    (
        "source_detail",
        "expected_status",
        "expected_code",
        "expected_message",
    ),
    [
        (
            "LOGIN_BAD_CREDENTIALS",
            401,
            "AUTH_INVALID_CREDENTIALS",
            "Invalid Email or Password.",
        ),
        (
            "LOGIN_USER_NOT_VERIFIED",
            403,
            "AUTH_NOT_VERIFIED",
            (
                "Please verify your email before "
                "logging in."
            ),
        ),
        (
            "REGISTER_USER_ALREADY_EXISTS",
            409,
            "AUTH_EMAIL_EXISTS",
            (
                "An account with that email already "
                "exists."
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_http_handler_maps_known_fastapi_users_errors(
    monkeypatch,
    registered_handlers,
    source_detail,
    expected_status,
    expected_code,
    expected_message,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    exception = HTTPException(
        status_code=400,
        detail=source_detail,
    )

    handler = registered_handlers[
        HTTPException
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == expected_status
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": expected_message,
        "detail": expected_code,
    }

    log_info.assert_called_once_with(
        "http mapped %s -> %s",
        source_detail,
        expected_code,
    )


@pytest.mark.asyncio
async def test_http_handler_returns_unmapped_string_detail(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()
    log_error = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )
    monkeypatch.setattr(
        errors.logger,
        "error",
        log_error,
    )

    exception = HTTPException(
        status_code=404,
        detail="Route not found",
    )

    handler = registered_handlers[
        HTTPException
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 404
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Route not found",
        "detail": "HTTP_EXCEPTION",
    }

    log_info.assert_called_once_with(
        "http error %s: %s",
        404,
        "Route not found",
    )
    log_error.assert_not_called()


@pytest.mark.asyncio
async def test_http_handler_logs_server_errors_at_error_level(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()
    log_error = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )
    monkeypatch.setattr(
        errors.logger,
        "error",
        log_error,
    )

    exception = HTTPException(
        status_code=503,
        detail="Service unavailable",
    )

    handler = registered_handlers[
        HTTPException
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 503
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Service unavailable",
        "detail": "HTTP_EXCEPTION",
    }

    log_error.assert_called_once_with(
        "http error %s: %s",
        503,
        "Service unavailable",
        exc_info=True,
    )
    log_info.assert_not_called()


@pytest.mark.asyncio
async def test_http_handler_uses_generic_message_for_non_string_detail(
    monkeypatch,
    registered_handlers,
):
    log_info = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "info",
        log_info,
    )

    detail = {
        "reason": "invalid state",
    }

    exception = HTTPException(
        status_code=400,
        detail=detail,
    )

    handler = registered_handlers[
        HTTPException
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 400
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Request failed.",
        "detail": "HTTP_EXCEPTION",
    }

    log_info.assert_called_once_with(
        "http error %s: %s",
        400,
        detail,
    )


@pytest.mark.asyncio
async def test_http_handler_logs_non_string_server_error(
    monkeypatch,
    registered_handlers,
):
    log_error = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "error",
        log_error,
    )

    detail = {
        "database": "unavailable",
    }

    exception = HTTPException(
        status_code=500,
        detail=detail,
    )

    handler = registered_handlers[
        HTTPException
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 500
    assert response_json(response)["message"] == (
        "Request failed."
    )
    assert response_json(response)["detail"] == (
        "HTTP_EXCEPTION"
    )

    log_error.assert_called_once_with(
        "http error %s: %s",
        500,
        detail,
        exc_info=True,
    )


@pytest.mark.asyncio
async def test_unexpected_handler_returns_500_and_logs_exception(
    monkeypatch,
    registered_handlers,
):
    log_error = MagicMock()

    monkeypatch.setattr(
        errors.logger,
        "error",
        log_error,
    )

    exception = RuntimeError(
        "unexpected failure"
    )

    handler = registered_handlers[
        Exception
    ]

    response = await handler(
        MagicMock(),
        exception,
    )

    assert response.status_code == 500
    assert response_json(response) == {
        "status": "error",
        "data": {},
        "message": "Internal server error",
        "detail": "INTERNAL_SERVER_ERROR",
    }

    log_error.assert_called_once_with(
        "unhandled: %s",
        exception,
        exc_info=True,
    )