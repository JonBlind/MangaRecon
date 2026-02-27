from __future__ import annotations

from backend.db.client_db import ClientReadDatabase
from backend.repositories.collections_repo import get_owned_collection_id
from backend.utils.domain_exceptions import NotFoundError

async def assert_owned_collection(user_db: ClientReadDatabase, *, user_id, collection_id: int) -> None:
    """
    Raise if collection_id is not owned by user_id.
    """
    owned = await get_owned_collection_id(user_db, user_id=user_id, collection_id=collection_id)
    if owned is None:
        raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")


def build_recommendations_cache_key(*, user_id, collection_id: int) -> str:
    return f"recommendations:{user_id}:{collection_id}"


async def cache_get_items(redis_cache, *, cache_key: str):
    return await redis_cache.get(cache_key)


async def cache_set_items(redis_cache, *, cache_key: str, items) -> None:
    await redis_cache.set(cache_key, items)
