import pytest
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import ValidationError

from backend.schemas.rating import RatingCreate, RatingRead


@pytest.mark.parametrize("val", ["0.0", "0.5", "1.0", "9.5", "10.0"])
def test_rating_create_accepts_valid(val: str):
    obj = RatingCreate(manga_id=1, personal_rating=Decimal(val))
    assert obj.manga_id == 1
    assert obj.personal_rating == Decimal(val)


@pytest.mark.parametrize("val", ["-0.5", "-1.0", "10.5", "11.0"])
def test_rating_create_rejects_out_of_range(val: str):
    with pytest.raises(ValidationError):
        RatingCreate(manga_id=1, personal_rating=Decimal(val))


@pytest.mark.parametrize("val", ["0.1", "1.2", "9.9"])
def test_rating_create_rejects_non_halves(val: str):
    with pytest.raises(ValidationError):
        RatingCreate(manga_id=1, personal_rating=Decimal(val))


def test_rating_create_requires_fields():
    with pytest.raises(ValidationError):
        RatingCreate()

def test_rating_read():
    now = datetime.now(timezone.utc)
    obj = RatingRead(manga_id=1, personal_rating=8.5, created_at=now)

    assert obj.manga_id == 1
    assert obj.personal_rating == 8.5
    assert obj.created_at == now

def test_rating_read_from_attributes():
    class FakeRating:
        def __init__(self):
            self.manga_id = 1
            self.personal_rating = 8.5
            self.created_at = datetime.now(timezone.utc)

    dummy = FakeRating()
    obj = RatingRead.model_validate(dummy)

    assert obj.manga_id == dummy.manga_id
    assert obj.personal_rating == dummy.personal_rating
    assert obj.created_at == dummy.created_at