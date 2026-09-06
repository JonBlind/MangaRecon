from __future__ import annotations

from typing import Literal

from sqlalchemy import select

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


async def list_collection_manga_ids(
    user_db: ClientReadDatabase,
    *,
    collection_id: int,
    order: Literal["asc", "desc"],
) -> list[int]:
    """Return every manga ID in a collection using stable membership order."""
    order_by = (
        MangaCollection.manga_id.asc()
        if order == "asc"
        else MangaCollection.manga_id.desc()
    )
    stmt = (
        select(MangaCollection.manga_id)
        .where(
            MangaCollection.collection_id == collection_id
        )
        .order_by(order_by)
    )
    result = await user_db.execute(stmt)
    return list(result.scalars().all())
