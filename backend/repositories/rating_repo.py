from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.db.models.rating import Rating


async def fetch_user_rating(user_db: ClientReadDatabase, *, user_id, manga_id: int) -> Rating | None:
    """
    Return user's rating for a manga if it exists, else None.
    """
    res = await user_db.execute(
        select(Rating).where(Rating.user_id == user_id, Rating.manga_id == manga_id)
    )
    return res.scalar_one_or_none()


async def list_user_ratings(
    user_db: ClientReadDatabase,
    *,
    user_id,
) -> list[Rating]:
    """Return every rating for a user in stable manga-ID order."""
    stmt = (
        select(Rating)
        .where(Rating.user_id == user_id)
        .order_by(Rating.manga_id.asc())
    )
    result = await user_db.execute(stmt)
    return list(result.scalars().all())


async def upsert_user_rating(user_db: ClientWriteDatabase, *, user_id, manga_id: int, score: float):
    """
    Upsert (create/update) rating using the DB wrapper.
    """
    return await user_db.rate_manga(user_id=user_id, manga_id=manga_id, score=score)
