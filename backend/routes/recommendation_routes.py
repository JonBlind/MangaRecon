'''
FastAPI routes for generating collection-based recommendations.

This router exposes ``GET /recommendations/{collection_id}`` which:
  1) Verifies the collection belongs to the authenticated (active, verified) user.
  2) Attempts to return a cached recommendation set from Redis.
  3) On cache miss, calls the recommendation generator and stores the result.
  4) Applies sorting and pagination over the in-memory result.
Returned payloads use the project-wide response envelope.
'''

from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy import select
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.db.models.user import User
from backend.db.models.collection import Collection
from backend.db.client_db import ClientReadDatabase
from backend.utils.ordering import OrderDirection , RecommendationOrderField
from backend.dependencies import get_user_read_db, get_public_read_db
from backend.cache.redis import get_redis_cache
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
from backend.recommendation.generator import generate_recommendations_for_collection, generate_recommendations_for_list
from backend.schemas.recommendation import RecommendationQueryListRequest
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])
redis_cache = get_redis_cache()

@router.get("/{collection_id}", response_model=dict)
@limiter.shared_limit("10/minute", scope="recs-ip-min")
@limiter.shared_limit("500/day",   scope="recs-ip-day")
async def get_recommendations_for_collection(
    request: Request,
    collection_id: int,
    order_by: RecommendationOrderField = Query("score"),
    order_dir: OrderDirection = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    '''
    Return paginated, ordered recommendations for the given collection.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier belonging to the current user.
        order_by (RecommendationOrderField): Field to order results by ("score" or "title").
        order_dir (OrderDirection): Sort direction ("asc" or "desc").
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        db (ClientReadDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.
    
    Returns:
        dict: Standardized response with total_results, page, size, and items.
    '''
    logger.info(f"Generating recommendations for collection: {collection_id}")
    try:
        exists = await db.execute(
            select(Collection.collection_id).where(
                Collection.collection_id == collection_id,
                Collection.user_id == user.id,
            )
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

        cache_key = f"recommendations:{user.id}:{collection_id}"
        cached_items = await redis_cache.get(cache_key)

        # seed metadata is only known when we run generator (cache miss)
        seed_total = None
        seed_used = None
        seed_truncated = None

        if cached_items is None:
            result = await generate_recommendations_for_collection(user.id, collection_id, db)
            items = result["items"]

            seed_total = result.get("seed_total")
            seed_used = result.get("seed_used")
            seed_truncated = result.get("seed_truncated")

            await redis_cache.set(cache_key, items)
        else:
            items = cached_items

        reverse = (order_dir == "desc")

        def key_func(item):
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

        offset = (page - 1) * size
        paginated = items[offset : offset + size]

        data = {
            "total_results": len(items),
            "page": page,
            "size": size,
            "items": paginated,
        }
        # only include these when known (cache miss)
        if seed_total is not None:
            data.update({
                "seed_total": seed_total,
                "seed_used": seed_used,
                "seed_truncated": seed_truncated,
            })

        return success("Recommendations generated successfully", data=data)

    except HTTPException:
        raise
    except ValueError as ve:
        logger.warning(f"Recommendation Skipped! (Likely due to no supplied manga): {ve}")
        return error("Recommendation Skipped!", detail=str(ve))
    except Exception as e:
        logger.error(
            f"Failed to generate recommendations for user {user.id} on collection {collection_id}: {e}",
            exc_info=True,
        )
        return error("Failed to generate recommendations", detail=str(e))
    
@router.post("/query-list")
@limiter.shared_limit("10/minute", scope="recs-ip-min")
@limiter.shared_limit("500/day", scope="recs-ip-day")
async def get_recommendations_for_query_list(
    request: Request,
    payload: RecommendationQueryListRequest,
    order_by: RecommendationOrderField = Query("score"),
    order_dir: OrderDirection = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientReadDatabase = Depends(get_public_read_db),
):
    '''
    Public endpoint: generate recommendations from a client-provided list of manga IDs.
    The list is not persisted.
    Args:
        request (Request): FastAPI request (required by rate limiting).
        collection_id (int): Collection identifier belonging to the current user.
        order_by (RecommendationOrderField): Field to order results by ("score" or "title").
        order_dir (OrderDirection): Sort direction ("asc" or "desc").
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        db (ClientReadDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.
    
    Returns:
        dict: Standardized response with total_results, page, size, and items.
    '''
    # de-dupe while preserving order
    seen = set()
    manga_ids: list[int] = []
    for mid in payload.manga_ids:
        if mid not in seen:
            seen.add(mid)
            manga_ids.append(mid)

    try:
        result = await generate_recommendations_for_list(manga_ids, db)
        items = result["items"]

        reverse = (order_dir == "desc")

        def key_func(item):
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

        offset = (page - 1) * size
        paginated = items[offset : offset + size]

        return success("Recommendations generated successfully", data={
            "seed_total": result["seed_total"],
            "seed_used": result["seed_used"],
            "seed_truncated": result["seed_truncated"],
            "total_results": len(items),
            "page": page,
            "size": size,
            "items": paginated,
        })

    except ValueError as ve:
        return error("Recommendation skipped", detail=str(ve))
    except Exception as e:
        logger.error("Failed to generate query-list recommendations", exc_info=True)
        return error("Failed to generate recommendations", detail=str(e))