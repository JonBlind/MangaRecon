from __future__ import annotations

import base64
from decimal import Decimal
import json
import logging
import zlib

from backend.db.client_db import ClientReadDatabase
from backend.repositories.collections_repo import get_owned_collection_id
from backend.utils.domain_exceptions import NotFoundError


logger = logging.getLogger(__name__)

_COMPRESSED_CACHE_PREFIX = "z1:"


async def assert_owned_collection(user_db: ClientReadDatabase, *, user_id, collection_id: int) -> None:
    """
    Raise if collection_id is not owned by user_id.
    """
    owned = await get_owned_collection_id(user_db, user_id=user_id, collection_id=collection_id)
    if owned is None:
        raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")


def build_recommendations_cache_key(
    *,
    user_id,
    collection_id: int,
    include_adult: bool = False,
) -> str:
    visibility = "adult" if include_adult else "safe"
    return f"recommendations:{user_id}:{collection_id}:{visibility}"


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _encode_recommendations_cache(payload: dict) -> str:
    serialized = json.dumps(
        payload,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    compressed = zlib.compress(serialized)
    encoded = base64.b64encode(compressed).decode("ascii")
    return f"{_COMPRESSED_CACHE_PREFIX}{encoded}"


def _decode_recommendations_cache(cached_value) -> dict | None:
    # Entries written before the compressed envelope was introduced contained
    # only an item list. Treat them as misses so the next request replaces them
    # with a complete payload that also includes seed metadata.
    if not isinstance(cached_value, str) or not cached_value.startswith(
        _COMPRESSED_CACHE_PREFIX
    ):
        return None

    try:
        encoded = cached_value.removeprefix(_COMPRESSED_CACHE_PREFIX)
        compressed = base64.b64decode(encoded, validate=True)
        serialized = zlib.decompress(compressed)
        payload = json.loads(serialized)
    except (ValueError, TypeError, UnicodeDecodeError, zlib.error, json.JSONDecodeError):
        logger.warning("Ignoring malformed recommendation cache payload")
        return None

    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("items"), list)
        or type(payload.get("seed_total")) is not int
        or type(payload.get("seed_used")) is not int
        or type(payload.get("seed_truncated")) is not bool
    ):
        logger.warning("Ignoring invalid recommendation cache envelope")
        return None

    return payload


async def cache_get_recommendations(redis_cache, *, cache_key: str) -> dict | None:
    cached_value = await redis_cache.get(cache_key)
    if cached_value is None:
        return None
    return _decode_recommendations_cache(cached_value)


async def cache_set_recommendations(
    redis_cache,
    *,
    cache_key: str,
    payload: dict,
) -> None:
    await redis_cache.set(cache_key, _encode_recommendations_cache(payload))
