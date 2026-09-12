from __future__ import annotations

from sqlalchemy import delete, select

from backend.db.client_db import ClientReadDatabase
from backend.db.models.collection import Collection
from backend.db.models.user import User


async def fetch_user_by_id(user_db: ClientReadDatabase, *, user_id) -> User | None:
    """
    Return the user row for user_id, else None.
    """
    res = await user_db.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()


async def fetch_user_for_deletion(user_db: ClientReadDatabase, *, user_id) -> User | None:
    """Lock the account while checking its password and deleting it."""
    res = await user_db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    return res.scalar_one_or_none()


async def get_owned_collection_ids(user_db: ClientReadDatabase, *, user_id) -> list[int]:
    """Capture cache keys before the owning collections are deleted."""
    return await user_db.scalars_all(
        select(Collection.collection_id).where(Collection.user_id == user_id)
    )


async def delete_user_row(user_db: ClientReadDatabase, *, user_id) -> None:
    """Use database FK cascades rather than loading every related ORM row."""
    await user_db.execute(delete(User).where(User.id == user_id))
