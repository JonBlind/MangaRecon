import pytest

from backend.utils.domain_exceptions import (
    BadRequestError,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)


def test_domain_error_stores_all_fields():
    detail = {
        "field": "collection_name",
        "reason": "duplicate",
    }

    error = DomainError(
        status_code=418,
        code="TEST_ERROR",
        message="Something went wrong.",
        detail=detail,
    )

    assert error.status_code == 418
    assert error.code == "TEST_ERROR"
    assert error.message == "Something went wrong."
    assert error.detail == detail


def test_domain_error_string_uses_message():
    error = DomainError(
        status_code=400,
        code="INVALID_REQUEST",
        message="The request was invalid.",
    )

    assert str(error) == "The request was invalid."
    assert error.args == (
        "The request was invalid.",
    )


def test_domain_error_defaults_detail_to_none():
    error = DomainError(
        status_code=400,
        code="INVALID_REQUEST",
        message="The request was invalid.",
    )

    assert error.detail is None


@pytest.mark.parametrize(
    (
        "exception_class",
        "expected_status",
    ),
    [
        (
            NotFoundError,
            404,
        ),
        (
            BadRequestError,
            400,
        ),
        (
            ConflictError,
            409,
        ),
        (
            ForbiddenError,
            403,
        ),
        (
            UnauthorizedError,
            401,
        ),
    ],
)
def test_specialized_domain_errors_use_expected_status_codes(
    exception_class,
    expected_status,
):
    error = exception_class(
        code="TEST_ERROR",
        message="Test message.",
    )

    assert isinstance(
        error,
        DomainError,
    )
    assert isinstance(
        error,
        Exception,
    )

    assert error.status_code == expected_status
    assert error.code == "TEST_ERROR"
    assert error.message == "Test message."
    assert error.detail is None
    assert str(error) == "Test message."


@pytest.mark.parametrize(
    "exception_class",
    [
        NotFoundError,
        BadRequestError,
        ConflictError,
        ForbiddenError,
        UnauthorizedError,
    ],
)
def test_specialized_domain_errors_preserve_detail(
    exception_class,
):
    detail = {
        "resource_id": 25,
    }

    error = exception_class(
        code="TEST_ERROR",
        message="Test message.",
        detail=detail,
    )

    assert error.detail == {
        "resource_id": 25,
    }


def test_not_found_error():
    error = NotFoundError(
        code="MANGA_NOT_FOUND",
        message="Manga not found.",
        detail={
            "manga_id": 25,
        },
    )

    assert error.status_code == 404
    assert error.code == "MANGA_NOT_FOUND"
    assert error.message == "Manga not found."
    assert error.detail == {
        "manga_id": 25,
    }


def test_bad_request_error():
    error = BadRequestError(
        code="INVALID_SCORE",
        message="Score was invalid.",
    )

    assert error.status_code == 400
    assert error.code == "INVALID_SCORE"


def test_conflict_error():
    error = ConflictError(
        code="COLLECTION_CONFLICT",
        message="Collection already exists.",
    )

    assert error.status_code == 409
    assert error.code == "COLLECTION_CONFLICT"


def test_forbidden_error():
    error = ForbiddenError(
        code="PROFILE_UPDATE_FORBIDDEN",
        message="This field cannot be updated.",
    )

    assert error.status_code == 403
    assert error.code == "PROFILE_UPDATE_FORBIDDEN"


def test_unauthorized_error():
    error = UnauthorizedError(
        code="AUTH_REQUIRED",
        message="Authentication required.",
    )

    assert error.status_code == 401
    assert error.code == "AUTH_REQUIRED"