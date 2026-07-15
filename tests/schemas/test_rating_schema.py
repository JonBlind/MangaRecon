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
        Decimal("0.0"),
        Decimal("0.5"),
        Decimal("1.0"),
        Decimal("5.0"),
        Decimal("9.5"),
        Decimal("10.0"),
        0,
        5,
        10,
        "7.5",
    ],
)
def test_rating_create_accepts_valid_half_point_values(
    rating,
):
    payload = RatingCreate(
        manga_id=10,
        personal_rating=rating,
    )

    assert payload.manga_id == 10
    assert (
        payload.personal_rating % Decimal("0.5")
        == Decimal("0")
    )


@pytest.mark.parametrize(
    "rating",
    [
        -0.5,
        -1,
        10.5,
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
        1.2,
        4.25,
        7.75,
        9.9,
    ],
)
def test_rating_create_rejects_non_half_point_values(
    rating,
):
    with pytest.raises(ValidationError):
        RatingCreate(
            manga_id=10,
            personal_rating=rating,
        )


def test_rating_create_stores_decimal():
    payload = RatingCreate(
        manga_id=10,
        personal_rating="8.5",
    )

    assert isinstance(
        payload.personal_rating,
        Decimal,
    )
    assert payload.personal_rating == Decimal("8.5")


def test_rating_create_requires_manga_id():
    with pytest.raises(ValidationError):
        RatingCreate(
            personal_rating=5.0,
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
        personal_rating=8.5,
        created_at=created_at,
    )

    assert rating.manga_id == 10
    assert rating.personal_rating == 8.5
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
        personal_rating=8.5,
        created_at=created_at,
    )

    rating = RatingRead.model_validate(
        orm_rating
    )

    assert rating.manga_id == 10
    assert rating.personal_rating == 8.5
    assert rating.created_at == created_at