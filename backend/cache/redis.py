import redis.asyncio as redis
import json
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    def __init__(self, host=None, port=None, db=None, password=None, ttl=None):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT"))
        self.db = db or int(os.getenv("REDIS_DB"))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.ttl = ttl or int(os.getenv("CACHE_TTL_SECONDS"))
        self.client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=True
        )

    async def set(self, key: str, value, ttl: int = None):
        try:
            await self.client.setex(key, ttl or self.ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")

    async def get(self, key: str):
        try:
            result = await self.client.get(key)
            return json.loads(result) if result else None
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    async def delete(self, key: str):
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")

    async def delete_multiple(self, *keys: str):
        if not keys:
            return
        try:
            await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE_MULTIPLE error for {keys[:3]}... : {e}")

    async def close_cache(self):
        await self.client.aclose()

redis_cache = RedisCache()