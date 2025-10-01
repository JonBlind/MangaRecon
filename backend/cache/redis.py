'''
Async Redis helper with JSON serialization and TTL defaults.

Provides a lightweight wrapper around redis.asyncio with convenience methods
for JSON (de)serialization, default TTL handling, and safe error logging.
'''


import redis.asyncio as redis
import json
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

class RedisCache:
    '''
    Lightweight async Redis helper with JSON serialization and TTL defaults.

    Args:
        host (str | None): Redis host; falls back to REDIS_HOST env.
        port (int | None): Redis port; falls back to REDIS_PORT env.
        db (int | None): Redis DB index; falls back to REDIS_DB env.
        password (str | None): Redis password; falls back to REDIS_PASSWORD env.
        ttl (int | None): Default TTL in seconds; falls back to CACHE_TTL_SECONDS env.

    Notes:
        - All methods log and fail soft (returning None / no-raise on errors).
        - Values are JSON-encoded on set and JSON-decoded on get.
    '''
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
        '''
        Set a JSON-serialized value with TTL.

        Args:
            key (str): Redis key.
            value (Any): JSON-serializable value to store.
            ttl (int | None): TTL override in seconds. Defaults to self.ttl.

        Returns:
            None: Value is stored in Redis or a warning is logged on failure.
        '''
        try:
            await self.client.setex(key, ttl or self.ttl, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}")

    async def get(self, key: str):
        '''
        Get and JSON-deserialize a value for the given key.

        Args:
            key (str): Redis key.

        Returns:
            Any | None: Decoded value on hit, or None on miss/decoding error.
        '''
        try:
            result = await self.client.get(key)
            return json.loads(result) if result else None
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}")
            return None

    async def delete(self, key: str):
        '''
        Delete a single key from Redis.

        Args:
            key (str): Redis key to delete.

        Returns:
            None
        '''
        try:
            await self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}")

    async def delete_multiple(self, *keys: str):
        '''
        Delete multiple keys in a single call. Safe to call with no keys.

        Args:
            *keys (str): One or more Redis keys to delete.

        Returns:
            None
        '''
        if not keys:
            return
        try:
            await self.client.delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE_MULTIPLE error for {keys[:3]}... : {e}")

    async def close_cache(self):
        '''
        Close the underlying Redis client connection (to be used on app shutdown).

        Returns:
            None
        '''
        await self.client.aclose()

# Shared cache instance used across the app
# Configured via environment variables.
redis_cache = RedisCache()