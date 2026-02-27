from __future__ import annotations

from sqlalchemy import select

from backend.db.client_db import ClientReadDatabase
from backend.db.models.user import User


async def fetch_user_by_id(user_db: ClientReadDatabase, *, user_id) -> User | None:
    """
    Return the user row for user_id, else None.
    """
    res = await user_db.execute(select(User).where(User.id == user_id))
    return res.scalar_one_or_none()