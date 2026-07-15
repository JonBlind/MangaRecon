import pytest

from backend.utils.response import error, success


def test_success_returns_expected_response_with_data():
    data = {
        "manga_id": 10,
        "title": "Berserk",
    }

    result = success(
        message="Manga retrieved successfully",
        data=data,
    )

    assert result == {
        "status": "success",
        "data": data,
        "message": "Manga retrieved successfully",
        "detail": None,
    }


def test_success_returns_empty_dict_when_data_is_none():
    result = success(
        message="Operation completed",
    )

    assert result == {
        "status": "success",
        "data": {},
        "message": "Operation completed",
        "detail": None,
    }


@pytest.mark.parametrize(
    "falsy_data",
    [
        {},
        None,
    ],
)
def test_success_normalizes_falsy_data_to_empty_dict(
    falsy_data,
):
    result = success(
        message="Operation completed",
        data=falsy_data,
    )

    assert result["data"] == {}


@pytest.mark.parametrize(
    "message",
    [
        "",
        None,
    ],
)
def test_success_rejects_missing_message(
    message,
):
    with pytest.raises(
        ValueError,
        match="Response Message CAN NOT be EMPTY",
    ):
        success(
            message=message,
            data={"value": 1},
        )


def test_error_returns_expected_response_with_data():
    data = {
        "field": "collection_name",
    }

    result = error(
        message="Collection creation failed",
        detail="A collection with that name already exists",
        data=data,
    )

    assert result == {
        "status": "error",
        "data": data,
        "message": "Collection creation failed",
        "detail": "A collection with that name already exists",
    }


def test_error_returns_empty_dict_when_data_is_none():
    result = error(
        message="Request failed",
        detail="Unexpected error",
    )

    assert result == {
        "status": "error",
        "data": {},
        "message": "Request failed",
        "detail": "Unexpected error",
    }


@pytest.mark.parametrize(
    "falsy_data",
    [
        {},
        None,
    ],
)
def test_error_normalizes_falsy_data_to_empty_dict(
    falsy_data,
):
    result = error(
        message="Request failed",
        detail="Unexpected error",
        data=falsy_data,
    )

    assert result["data"] == {}


@pytest.mark.parametrize(
    "message",
    [
        "",
        None,
    ],
)
def test_error_rejects_missing_message_before_validating_detail(
    message,
):
    with pytest.raises(
        ValueError,
        match="Response Message CAN NOT be EMPTY",
    ):
        error(
            message=message,
            detail="A detail exists",
        )


@pytest.mark.parametrize(
    "detail",
    [
        "",
        None,
    ],
)
def test_error_rejects_missing_detail(
    detail,
):
    with pytest.raises(
        ValueError,
        match="Detail Field CAN NOT be EMPTY for errors",
    ):
        error(
            message="Request failed",
            detail=detail,
        )


def test_error_validates_message_before_detail_when_both_are_missing():
    with pytest.raises(
        ValueError,
        match="Response Message CAN NOT be EMPTY",
    ):
        error(
            message="",
            detail="",
        )