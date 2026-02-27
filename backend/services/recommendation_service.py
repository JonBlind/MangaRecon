from __future__ import annotations

from typing import Literal

from backend.db.client_db import ClientReadDatabase
from backend.repositories.recommendation_repo import (
    assert_owned_collection,
    build_recommendations_cache_key,
    cache_get_items,
    cache_set_items,
)
from backend.recommendation.generator import generate_recommendations_for_collection, generate_recommendations_for_list
from backend.utils.domain_exceptions import BadRequestError

def _sort_items(items: list[dict], *, order_by, order_dir) -> None:
    reverse = (order_dir == "desc")

    def key_func(item: dict):
        if order_by == "score":
            return item.get("score", float("-inf"))
        if order_by == "title":
            return (item.get("title") or "").casefold()
        val = item.get(order_by)
        return val if val is not None else float("-inf")

    items.sort(
        key=lambda x: (key_func(x), (x.get("title") or "").casefold()),
        reverse=reverse,
    )


async def get_recommendations_for_collection_page(
    *,
    user_id,
    collection_id: int,
    order_by,
    order_dir: Literal["asc", "desc"],
    page: int,
    size: int,
    user_db: ClientReadDatabase,
    redis_cache,
) -> dict:
    """
    Return paginated, ordered recommendations for the given collection.
    """
    await assert_owned_collection(user_db, user_id=user_id, collection_id=collection_id)

    cache_key = build_recommendations_cache_key(user_id=user_id, collection_id=collection_id)
    cached_items = await cache_get_items(redis_cache, cache_key=cache_key)

    # seed metadata is only known when we run generator (cache miss)
    seed_total = None
    seed_used = None
    seed_truncated = None

    if cached_items is None:
        result = await generate_recommendations_for_collection(user_id, collection_id, user_db)
        items = result["items"]

        seed_total = result.get("seed_total")
        seed_used = result.get("seed_used")
        seed_truncated = result.get("seed_truncated")

        await cache_set_items(redis_cache, cache_key=cache_key, items=items)
    else:
        items = cached_items

    _sort_items(items, order_by=order_by, order_dir=order_dir)

    offset = (page - 1) * size
    paginated = items[offset : offset + size]

    data = {
        "total_results": len(items),
        "page": page,
        "size": size,
        "items": paginated,
    }

    if seed_total is not None:
        data.update({
            "seed_total": seed_total,
            "seed_used": seed_used,
            "seed_truncated": seed_truncated,
        })

    return data


async def get_recommendations_for_query_list_page(
    *,
    manga_ids: list[int],
    order_by,
    order_dir: Literal["asc", "desc"],
    page: int,
    size: int,
    db: ClientReadDatabase,
) -> dict:
    """
    Public: generate recommendations from a client-provided list of manga IDs.
    The list is not persisted.
    """
    if not manga_ids:
        raise BadRequestError(code="RECOMMENDATION_SEED_EMPTY", message="Need at least 1 manga in the list to generate recommendations.",)
    
    # de-dupe while preserving order
    seen = set()
    deduped: list[int] = []
    for mid in manga_ids:
        if mid not in seen:
            seen.add(mid)
            deduped.append(mid)

    result = await generate_recommendations_for_list(deduped, db)
    items = result["items"]

    _sort_items(items, order_by=order_by, order_dir=order_dir)

    offset = (page - 1) * size
    paginated = items[offset : offset + size]

    return {
        "seed_total": result["seed_total"],
        "seed_used": result["seed_used"],
        "seed_truncated": result["seed_truncated"],
        "total_results": len(items),
        "page": page,
        "size": size,
        "items": paginated,
    }