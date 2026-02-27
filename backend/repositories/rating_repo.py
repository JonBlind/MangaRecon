from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select

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


async def count_user_ratings(user_db: ClientReadDatabase, *, user_id) -> int:
    """
    Count total ratings for a user.
    """
    base = select(Rating).where(Rating.user_id == user_id)
    count_stmt = base.with_only_columns(func.count()).order_by(None)
    res = await user_db.execute(count_stmt)
    return res.scalar_one()


async def page_user_ratings(user_db: ClientReadDatabase, *, user_id, offset: int, limit: int) -> list[Rating]:
    """
    Return a page of Rating ORM rows for a user.
    """
    stmt = (
        select(Rating)
        .where(Rating.user_id == user_id)
        .order_by(Rating.manga_id.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await user_db.execute(stmt)
    return list(res.scalars().all())


async def upsert_user_rating(user_db: ClientWriteDatabase, *, user_id, manga_id: int, score: float):
    """
    Upsert (create/update) rating using the DB wrapper.
    """
    return await user_db.rate_manga(user_id=user_id, manga_id=manga_id, score=score)
