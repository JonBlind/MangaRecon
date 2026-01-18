'''
Async Redis helper with JSON serialization and TTL defaults.

Provides a lightweight wrapper around redis.asyncio with convenience methods
for JSON (de)serialization, default TTL handling, and safe error logging.
'''

from redis.asyncio import Redis
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedisCache:
    '''
    Lightweight async Redis helper with JSON serialization and TTL defaults.

    Args:
        host (str | None): Redis host; falls back to REDIS_HOST env.
        port (int | None): Redis port; falls back to REDIS_PORT env.
        db (int | None): Redis DB index; falls back to REDIS_DB env.
        password (str | None): Redis password; falls back to REDIS_PASSWORD env.
        ttl_default (int | None): Default TTL in seconds; falls back to CACHE_TTL_SECONDS env.

    Notes:
        - All methods log and fail soft (returning None / no-raise on errors).
        - Values are JSON-encoded on set and JSON-decoded on get.
    '''
    def __init__(self, host=None, port=None, db=None, password=None, ttl_default=None):
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._ttl_default = ttl_default
        self._client: Redis | None = None

    def _get_client(self) -> Redis:
        '''
        Singleton implementation. This method returns the client if one exists; otherwise, creates one based on env.
        
        Args:
            self
        Returns:
            client instance of this redis cache.
        '''
        if self._client is None:
            host = self._host or os.getenv("REDIS_HOST", "localhost")
            port = self._port if self._port is not None else int(os.getenv("REDIS_PORT", "6379"))
            db = self._db if self._db is not None else int(os.getenv("REDIS_DB", "0"))
            password = self._password or os.getenv("REDIS_PASSWORD")

            self._client = Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,  # returns str, not bytes
            )
        return self._client
    
    def _resolve_ttl(self, ttl: int | None) -> int | None:
        if ttl is not None:
            return ttl
        if self._ttl_default is not None:
            return self._ttl_default
        ttl_env = os.getenv("CACHE_TTL_SECONDS")
        return int(ttl_env) if ttl_env else None

    async def set(self, key: str, value, ttl: int | None = None):
        '''
        Set a JSON-serialized value with TTL.

        Args:
            key (str): Redis key.
            value (Any): JSON-serializable value to store.
            ttl (int | None): TTL override in seconds. Defaults to cache TTL default.

        Returns:
            None: Value is stored in Redis or a warning is logged on failure.
        '''
        try:
            payload = json.dumps(value, default=str)
            ex = self._resolve_ttl(ttl)
            await self._get_client().set(key, payload, ex=ex)
        except Exception as e:
            logger.warning(f"Redis SET error for {key}: {e}", exc_info=True)

    async def get(self, key: str):
        '''
        Get and JSON-deserialize a value for the given key.

        Args:
            key (str): Redis key.

        Returns:
            Any | None: Decoded value on hit, or None on miss/decoding error.
        '''
        try:
            raw = await self._get_client().get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis GET error for {key}: {e}", exc_info=True)
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
            await self._get_client().delete(key)
        except Exception as e:
            logger.warning(f"Redis DELETE error for {key}: {e}", exc_info=True)

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
            await self._get_client().delete(*keys)
        except Exception as e:
            logger.warning(f"Redis DELETE_MULTIPLE error for {keys[:3]}... : {e}", exc_info=True)

    async def close(self):
        '''
        Close the underlying Redis client connection (to be used on app shutdown).

        Returns:
            None
        '''
        if self._client is not None:
            await self._client.close()
            self._client = None

# Shared cache instance used across the app
_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    '''
    Helper method accessible by the app. Grab the current, or make a new redis cache.
    
    :return: Description
    :rtype: RedisCache
    '''
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache