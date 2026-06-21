from backend.utils.response import success, error


def test_success_response_with_data():
    response = success("Created successfully", data={"id": 1})

    assert response == {
        "status": "success",
        "data": {"id": 1},
        "message": "Created successfully",
        "detail": None,
    }


def test_error_response_with_detail():
    response = error("Service unavailable.", detail="TEMPORARILY_UNAVAILABLE")

    assert response == {
        "status": "error",
        "data": {},
        "message": "Service unavailable.",
        "detail": "TEMPORARILY_UNAVAILABLE",
    }