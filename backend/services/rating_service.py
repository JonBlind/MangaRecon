from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError

from backend.cache.invalidation import invalidate_user_recommendations
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.repositories.rating_repo import (
    fetch_user_rating,
    count_user_ratings,
    page_user_ratings,
    upsert_user_rating,
)
from backend.schemas.rating import RatingCreate, RatingRead
from backend.utils.domain_exceptions import NotFoundError


async def create_or_update_rating(
    *,
    user_id,
    payload: RatingCreate,
    user_db: ClientWriteDatabase,
) -> RatingRead:
    """
    Create or update a user's rating for a manga.
    """
    try:
        result = await upsert_user_rating(
            user_db,
            user_id=user_id,
            manga_id=payload.manga_id,
            score=float(payload.personal_rating),
        )
        await invalidate_user_recommendations(user_db, user_id)
        return RatingRead.model_validate(result)

    except IntegrityError:
        await user_db.rollback()
        raise NotFoundError(code="MANGA_NOT_FOUND", message="Manga not found.")


async def update_existing_rating(
    *,
    user_id,
    payload: RatingCreate,
    user_db: ClientWriteDatabase,
) -> RatingRead:
    """
    Update a rating only if it already exists.
    """
    existing = await user_db.get_user_rating_for_manga(user_id, payload.manga_id)
    if not existing:
        raise NotFoundError(code="RATING_NOT_FOUND", message="Rating not found.")

    try:
        result = await upsert_user_rating(
            user_db,
            user_id=user_id,
            manga_id=payload.manga_id,
            score=float(payload.personal_rating),
        )
        await invalidate_user_recommendations(user_db, user_id)
        return RatingRead.model_validate(result)

    except IntegrityError:
        await user_db.rollback()
        raise NotFoundError(code="MANGA_NOT_FOUND", message="Manga not found.")


async def delete_user_rating_for_manga(
    *,
    user_id,
    manga_id: int,
    user_db: ClientWriteDatabase,
) -> dict:
    """
    Delete user's rating for a manga if it exists.
    """
    existing = await user_db.get_user_rating_for_manga(user_id, manga_id)
    if not existing:
        raise NotFoundError(code="RATING_NOT_FOUND", message="Rating not found.")

    await user_db.delete_rating(user_id=user_id, manga_id=manga_id)

    await invalidate_user_recommendations(user_db, user_id)
    return {"manga_id": manga_id}


async def get_user_ratings_page(
    *,
    user_id,
    page: int,
    size: int,
    user_db: ClientReadDatabase,
) -> dict:
    """
    Paginated list of a user's ratings.
    """
    offset = (page - 1) * size
    total = await count_user_ratings(user_db, user_id=user_id)
    rows = await page_user_ratings(user_db, user_id=user_id, offset=offset, limit=size)
    items = [RatingRead.model_validate(r) for r in rows]
    return {"total_results": total, "page": page, "size": size, "items": items}


async def get_single_user_rating(
    *,
    user_id,
    manga_id: int,
    user_db: ClientReadDatabase,
) -> RatingRead:
    """
    Return a single rating for a user/manga pair.
    """
    rating = await fetch_user_rating(user_db, user_id=user_id, manga_id=manga_id)
    if not rating:
        raise NotFoundError(code="RATING_NOT_FOUND", message="Rating not found.")
    return RatingRead.model_validate(rating)