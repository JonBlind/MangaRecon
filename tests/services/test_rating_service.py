from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.schemas.rating import RatingCreate
from backend.services import rating_service
from backend.utils.domain_exceptions import NotFoundError


def make_rating(
    *,
    manga_id: int = 10,
    personal_rating: float = 8.5,
):
    return SimpleNamespace(
        manga_id=manga_id,
        personal_rating=personal_rating,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def make_write_db():
    db = MagicMock()
    db.rollback = AsyncMock()
    db.get_user_rating_for_manga = AsyncMock()
    db.delete_rating = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_or_update_rating_returns_validated_rating(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user_db = make_write_db()
    manga_db = MagicMock()

    stored_rating = make_rating(
        manga_id=15,
        personal_rating=8.5,
    )

    manga_exists = AsyncMock(return_value=True)
    upsert = AsyncMock(return_value=stored_rating)
    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "manga_exists",
        manga_exists,
    )
    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    result = await rating_service.create_or_update_rating(
        user_id=user_id,
        payload=RatingCreate(
            manga_id=15,
            personal_rating=Decimal("8.5"),
        ),
        user_db=user_db,
        manga_db=manga_db,
    )

    assert result.manga_id == 15
    assert result.personal_rating == 8.5
    assert result.created_at == stored_rating.created_at

    manga_exists.assert_awaited_once_with(
        manga_db,
        manga_id=15,
    )

    upsert.assert_awaited_once_with(
        user_db,
        user_id=user_id,
        manga_id=15,
        score=8.5,
    )

    invalidate.assert_awaited_once_with(
        user_db,
        user_id,
    )

    user_db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_or_update_rating_converts_integrity_error(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user_db = make_write_db()
    manga_db = MagicMock()

    manga_exists = AsyncMock(return_value=True)

    upsert = AsyncMock(
        side_effect=IntegrityError(
            "INSERT",
            {},
            Exception("foreign key violation"),
        )
    )

    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "manga_exists",
        manga_exists,
    )
    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.create_or_update_rating(
            user_id=user_id,
            payload=RatingCreate(
                manga_id=999,
                personal_rating=Decimal("7.0"),
            ),
            user_db=user_db,
            manga_db=manga_db,
        )

    error = exc_info.value

    assert error.status_code == 404
    assert error.code == "MANGA_NOT_FOUND"
    assert error.message == "Manga not found."

    manga_exists.assert_awaited_once_with(
        manga_db,
        manga_id=999,
    )

    user_db.rollback.assert_awaited_once()
    invalidate.assert_not_awaited()

@pytest.mark.asyncio
async def test_create_or_update_rating_rejects_missing_manga(
    monkeypatch,
):
    user_id = uuid.uuid4()
    user_db = make_write_db()
    manga_db = MagicMock()

    manga_exists = AsyncMock(return_value=False)
    upsert = AsyncMock()
    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "manga_exists",
        manga_exists,
    )
    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.create_or_update_rating(
            user_id=user_id,
            payload=RatingCreate(
                manga_id=999,
                personal_rating=Decimal("7.0"),
            ),
            user_db=user_db,
            manga_db=manga_db,
        )

    assert exc_info.value.code == "MANGA_NOT_FOUND"

    manga_exists.assert_awaited_once_with(
        manga_db,
        manga_id=999,
    )

    upsert.assert_not_awaited()
    invalidate.assert_not_awaited()

@pytest.mark.asyncio
async def test_update_existing_rating_raises_when_rating_missing(
    monkeypatch,
):
    db = make_write_db()
    db.get_user_rating_for_manga.return_value = None

    upsert = AsyncMock()
    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.update_existing_rating(
            user_id=uuid.uuid4(),
            payload=RatingCreate(
                manga_id=25,
                personal_rating=Decimal("6.5"),
            ),
            user_db=db,
        )

    error = exc_info.value

    assert error.code == "RATING_NOT_FOUND"
    assert error.message == "Rating not found."

    upsert.assert_not_awaited()
    invalidate.assert_not_awaited()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_existing_rating_updates_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = make_write_db()
    db.get_user_rating_for_manga.return_value = make_rating(
        manga_id=25,
        personal_rating=5.0,
    )

    updated_rating = make_rating(
        manga_id=25,
        personal_rating=9.0,
    )

    upsert = AsyncMock(return_value=updated_rating)
    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    result = await rating_service.update_existing_rating(
        user_id=user_id,
        payload=RatingCreate(
            manga_id=25,
            personal_rating=Decimal("9.0"),
        ),
        user_db=db,
    )

    db.get_user_rating_for_manga.assert_awaited_once_with(
        user_id,
        25,
    )
    upsert.assert_awaited_once_with(
        db,
        user_id=user_id,
        manga_id=25,
        score=9.0,
    )
    invalidate.assert_awaited_once_with(db, user_id)

    assert result.manga_id == 25
    assert result.personal_rating == 9.0
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_existing_rating_converts_integrity_error(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = make_write_db()
    db.get_user_rating_for_manga.return_value = make_rating(
        manga_id=25,
    )

    upsert = AsyncMock(
        side_effect=IntegrityError(
            "UPDATE",
            {},
            Exception("foreign key violation"),
        )
    )
    invalidate = AsyncMock()

    monkeypatch.setattr(
        rating_service,
        "upsert_user_rating",
        upsert,
    )
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.update_existing_rating(
            user_id=user_id,
            payload=RatingCreate(
                manga_id=25,
                personal_rating=Decimal("8.0"),
            ),
            user_db=db,
        )

    assert exc_info.value.code == "MANGA_NOT_FOUND"
    assert exc_info.value.message == "Manga not found."

    db.rollback.assert_awaited_once()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_rating_raises_when_missing(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = make_write_db()
    db.get_user_rating_for_manga.return_value = None

    invalidate = AsyncMock()
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.delete_user_rating_for_manga(
            user_id=user_id,
            manga_id=30,
            user_db=db,
        )

    assert exc_info.value.code == "RATING_NOT_FOUND"
    assert exc_info.value.message == "Rating not found."

    db.delete_rating.assert_not_awaited()
    invalidate.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_rating_deletes_and_invalidates(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = make_write_db()
    db.get_user_rating_for_manga.return_value = make_rating(
        manga_id=30,
    )

    invalidate = AsyncMock()
    monkeypatch.setattr(
        rating_service,
        "invalidate_user_recommendations",
        invalidate,
    )

    result = await rating_service.delete_user_rating_for_manga(
        user_id=user_id,
        manga_id=30,
        user_db=db,
    )

    assert result == {"manga_id": 30}

    db.get_user_rating_for_manga.assert_awaited_once_with(
        user_id,
        30,
    )
    db.delete_rating.assert_awaited_once_with(
        user_id=user_id,
        manga_id=30,
    )
    invalidate.assert_awaited_once_with(db, user_id)


@pytest.mark.asyncio
async def test_get_user_ratings_page_returns_paginated_ratings(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = MagicMock()

    ratings = [
        make_rating(
            manga_id=1,
            personal_rating=7.5,
        ),
        make_rating(
            manga_id=2,
            personal_rating=9.0,
        ),
    ]

    count_ratings = AsyncMock(return_value=12)
    page_ratings = AsyncMock(return_value=ratings)

    monkeypatch.setattr(
        rating_service,
        "count_user_ratings",
        count_ratings,
    )
    monkeypatch.setattr(
        rating_service,
        "page_user_ratings",
        page_ratings,
    )

    result = await rating_service.get_user_ratings_page(
        user_id=user_id,
        page=2,
        size=5,
        user_db=db,
    )

    assert result["total_results"] == 12
    assert result["page"] == 2
    assert result["size"] == 5
    assert [item.manga_id for item in result["items"]] == [1, 2]
    assert [
        item.personal_rating
        for item in result["items"]
    ] == [7.5, 9.0]

    count_ratings.assert_awaited_once_with(
        db,
        user_id=user_id,
    )
    page_ratings.assert_awaited_once_with(
        db,
        user_id=user_id,
        offset=5,
        limit=5,
    )


@pytest.mark.asyncio
async def test_get_user_ratings_page_handles_empty_page(
    monkeypatch,
):
    db = MagicMock()

    monkeypatch.setattr(
        rating_service,
        "count_user_ratings",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        rating_service,
        "page_user_ratings",
        AsyncMock(return_value=[]),
    )

    result = await rating_service.get_user_ratings_page(
        user_id=uuid.uuid4(),
        page=1,
        size=10,
        user_db=db,
    )

    assert result == {
        "total_results": 0,
        "page": 1,
        "size": 10,
        "items": [],
    }


@pytest.mark.asyncio
async def test_get_single_user_rating_returns_rating(
    monkeypatch,
):
    user_id = uuid.uuid4()
    db = MagicMock()
    rating = make_rating(
        manga_id=44,
        personal_rating=6.0,
    )

    fetch_rating = AsyncMock(return_value=rating)
    monkeypatch.setattr(
        rating_service,
        "fetch_user_rating",
        fetch_rating,
    )

    result = await rating_service.get_single_user_rating(
        user_id=user_id,
        manga_id=44,
        user_db=db,
    )

    assert result.manga_id == 44
    assert result.personal_rating == 6.0

    fetch_rating.assert_awaited_once_with(
        db,
        user_id=user_id,
        manga_id=44,
    )


@pytest.mark.asyncio
async def test_get_single_user_rating_raises_when_missing(
    monkeypatch,
):
    fetch_rating = AsyncMock(return_value=None)
    monkeypatch.setattr(
        rating_service,
        "fetch_user_rating",
        fetch_rating,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await rating_service.get_single_user_rating(
            user_id=uuid.uuid4(),
            manga_id=44,
            user_db=MagicMock(),
        )

    assert exc_info.value.code == "RATING_NOT_FOUND"
    assert exc_info.value.message == "Rating not found."