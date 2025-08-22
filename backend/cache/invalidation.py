from sqlalchemy.future import select
from backend.db.models.collection import Collection
from backend.cache.redis import redis_cache

async def invalidate_user_recommendations(db, user_id: int):
    res = await db.session.execute(
        select(Collection.collection_id).where(Collection.user_id == user_id)
    )
    keys = [f"recommendations:{user_id}:{cid}" for (cid,) in res.all()]
    if keys:
        await redis_cache.delete_many(*keys)

async def invalidate_collection_recommendations(user_id: int, collection_id: int):
    await redis_cache.delete(f"recommendations:{user_id}:{collection_id}")