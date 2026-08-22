'''
Async Redis helper with JSON serialization and TTL defaults.

Provides a lightweight wrapper around redis.asyncio with convenience methods
for JSON (de)serialization, default TTL handling, and safe error logging.
'''

import asyncio
import json
import logging
import os
from typing import Optional
from urllib.parse import urlparse

from redis.asyncio import Redis

from backend.config.settings import settings as app_settings

logger = logging.getLogger(__name__)

DEFAULT_REDIS_URL = "redis://localhost:6379/0"
SUPPORTED_REDIS_SCHEMES = {"redis", "rediss"}


def get_redis_url(*, required: bool = False) -> str:
    """
    Resolve and validate the shared Redis connection URL.

    Production callers pass ``required=True`` so a missing Redis
    configuration fails during application startup. Local development and
    tests may use the default local Redis instance.
    """
    url = os.getenv("REDIS_URL")

    if not url:
        if required:
            raise RuntimeError("REDIS_URL must be set when MANGARECON_ENV=prod.")
        return DEFAULT_REDIS_URL

    scheme = urlparse(url).scheme.lower()
    if scheme not in SUPPORTED_REDIS_SCHEMES:
        raise RuntimeError("REDIS_URL must use the redis:// or rediss:// scheme.")

    return url


class RedisCache:
    '''
    Lightweight async Redis helper with JSON serialization and TTL defaults.

    Args:
        url (str | None): Redis URL; falls back to REDIS_URL and then the
            local development default.
        ttl_default (int | None): Default TTL in seconds; falls back to CACHE_TTL_SECONDS env.

    Notes:
        - All methods log and fail soft (returning None / no-raise on errors).
        - Values are JSON-encoded on set and JSON-decoded on get.
        - Both redis:// and TLS-enabled rediss:// URLs are supported.
    '''
    def __init__(self, url=None, ttl_default=None):
        self._url = url
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
            url = self._url or get_redis_url()

            if self._url is not None:
                scheme = urlparse(self._url).scheme.lower()
                if scheme not in SUPPORTED_REDIS_SCHEMES:
                    raise RuntimeError("Redis URL must use the redis:// or rediss:// scheme.")

            self._client = Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=(
                    app_settings.redis_connect_timeout_seconds
                ),
                socket_timeout=(
                    app_settings.redis_operation_timeout_seconds
                ),
                max_connections=app_settings.redis_max_connections,
            )
        return self._client

    def get_client(self) -> Redis:
        """Return the shared client for callers that own error handling."""
        return self._get_client()
    
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

    async def ping(self, timeout: float | None = None) -> bool:
        resolved_timeout = (
            app_settings.redis_ready_timeout_seconds
            if timeout is None
            else timeout
        )
        try:
            result = await asyncio.wait_for(
                self._get_client().ping(),
                timeout=resolved_timeout,
            )
            return bool(result)
        except Exception:
            return False

    async def close(self):
        '''
        Close the underlying Redis client connection (to be used on app shutdown).

        Returns:
            None
        '''
        if self._client is not None:
            await self._client.aclose()
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
