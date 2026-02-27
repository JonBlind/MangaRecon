from __future__ import annotations

from typing import Literal

from sqlalchemy import func, select

from backend.db.client_db import ClientReadDatabase
from backend.db.models.collection import Collection
from backend.db.models.manga_collection import MangaCollection


async def get_owned_collection_id(user_db: ClientReadDatabase, *, user_id, collection_id: int) -> int | None:
    """
    Return the collection_id if it exists and is owned by user_id, else None.
    """
    stmt = select(Collection.collection_id).where(
        Collection.collection_id == collection_id,
        Collection.user_id == user_id,
    )
    res = await user_db.execute(stmt)
    return res.scalar_one_or_none()


async def count_collection_manga(user_db: ClientReadDatabase, *, collection_id: int) -> int:
    """
    Count number of manga rows in a collection via membership table.
    """
    stmt = select(func.count(MangaCollection.manga_id)).where(
        MangaCollection.collection_id == collection_id
    )
    res = await user_db.execute(stmt)
    return res.scalar_one()


async def page_collection_manga_ids(user_db: ClientReadDatabase, *, collection_id: int, offset: int, limit: int, order: Literal["asc", "desc"],) -> list[int]:
    """
    Return a page of manga_ids from the membership table.
    """
    order_by = MangaCollection.manga_id.asc() if order == "asc" else MangaCollection.manga_id.desc()
    stmt = (
        select(MangaCollection.manga_id)
        .where(MangaCollection.collection_id == collection_id)
        .order_by(order_by)
        .offset(offset)
        .limit(limit)
    )
    res = await user_db.execute(stmt)
    return list(res.scalars().all())