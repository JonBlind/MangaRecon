from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.schemas.rating import (
    RatingCreate,
    RatingRead,
)


@pytest.mark.parametrize(
    "rating",
    [
        Decimal("1.0"),
        Decimal("5.0"),
        Decimal("10.0"),
        1,
        5,
        10,
        8.0,
        "7",
    ],
)
def test_rating_create_accepts_integer_scores_from_one_to_ten(
    rating,
):
    payload = RatingCreate(
        manga_id=10,
        personal_rating=rating,
    )

    assert payload.manga_id == 10
    assert isinstance(payload.personal_rating, int)
    assert 1 <= payload.personal_rating <= 10


@pytest.mark.parametrize(
    "rating",
    [
        0,
        -1,
        11,
        20,
    ],
)
def test_rating_create_rejects_out_of_range_values(
    rating,
):
    with pytest.raises(ValidationError):
        RatingCreate(
            manga_id=10,
            personal_rating=rating,
        )


@pytest.mark.parametrize(
    "rating",
    [
        0.1,
        0.5,
        1.2,
        4.25,
        7.5,
        7.75,
        9.9,
    ],
)
def test_rating_create_rejects_non_integer_values(
    rating,
):
    with pytest.raises(ValidationError):
        RatingCreate(
            manga_id=10,
            personal_rating=rating,
        )


def test_rating_create_stores_integer():
    payload = RatingCreate(
        manga_id=10,
        personal_rating="8",
    )

    assert isinstance(payload.personal_rating, int)
    assert payload.personal_rating == 8


def test_rating_create_requires_manga_id():
    with pytest.raises(ValidationError):
        RatingCreate(
            personal_rating=5,
        )


def test_rating_create_requires_personal_rating():
    with pytest.raises(ValidationError):
        RatingCreate(
            manga_id=10,
        )


def test_rating_read_accepts_valid_data():
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )

    rating = RatingRead(
        manga_id=10,
        personal_rating=8.0,
        created_at=created_at,
    )

    assert rating.manga_id == 10
    assert rating.personal_rating == 8.0
    assert rating.created_at == created_at


def test_rating_read_supports_from_attributes():
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )

    orm_rating = SimpleNamespace(
        manga_id=10,
        personal_rating=8.0,
        created_at=created_at,
    )

    rating = RatingRead.model_validate(
        orm_rating
    )

    assert rating.manga_id == 10
    assert rating.personal_rating == 8.0
    assert rating.created_at == created_at
