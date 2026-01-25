'''
Cache invalidation helpers for recommendation results.
This module centralizes *targeted* cache invalidation for recommendations
stored in Redis. We maintain keys in the format:
recommendations:{user_id}:{collection_id}
'''
from sqlalchemy import select
from backend.db.models.collection import Collection
from backend.cache.redis import get_redis_cache
from backend.db.client_db import ClientReadDatabase

redis_cache = get_redis_cache()

async def invalidate_user_recommendations(db: ClientReadDatabase, user_id: int):
    '''
    Invalidate all cached recommendation payloads for a user.

    Args:
        user_id (uuid.UUID): Identifier of the user whose recommendation cache should be cleared.

    Returns:
        None: Performs side effects on the cache (deletes keys), does not return data.
    '''
    res = await db.execute(
        select(Collection.collection_id).where(Collection.user_id == user_id)
    )
    keys = [f"recommendations:{user_id}:{cid}" for (cid,) in res.all()]
    if keys:
        await redis_cache.delete_multiple(*keys)

async def invalidate_collection_recommendations(user_id: int, collection_id: int):
    '''
    Invalidate the cached recommendation payload for a specific user collection.

    Args:
        user_id (uuid.UUID): Owner of the collection.
        collection_id (int): Target collection whose recommendation cache should be cleared.

    Returns:
        None: Performs side effects on the cache (deletes keys), does not return data.
    '''
    await redis_cache.delete(f"recommendations:{user_id}:{collection_id}")