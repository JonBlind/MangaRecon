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
from sqlalchemy.ext.asyncio import AsyncSession
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.db.models.user import User
from backend.db.models.collection import Collection
from backend.utils.ordering import OrderDirection , RecommendationOrderField
from backend.dependencies import get_user_read_db
from backend.cache.redis import redis_cache
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
from backend.recommendation.generator import generate_recommendations
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{collection_id}", response_model=dict)
@limiter.shared_limit("30/minute", scope="recs-ip-min")
@limiter.shared_limit("500/day",   scope="recs-ip-day")
async def get_recommendations_for_collection(
    request: Request,
    collection_id: int,
    order_by: RecommendationOrderField = Query("score"),
    order_dir: OrderDirection = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db = Depends(get_user_read_db),
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
        db (ClientDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.
    
    Returns:
        dict: Standardized response with total_results, page, size, and items.
    '''
    logger.info(f"Generating recommendations for collection: {collection_id}")
    try:

        exists = await db.session.execute(
            select(Collection.collection_id).where(Collection.collection_id == collection_id,
                                                Collection.user_id == user.id)
        )
        if exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
        
        cache_key = f"recommendations:{user.id}:{collection_id}"
        recommendations = await redis_cache.get(cache_key)
        
        if recommendations is None:
            recommendations = await generate_recommendations(user.id, collection_id, db.session)
            await redis_cache.set(cache_key, recommendations)

        reverse = (order_dir == "desc")

        # If we get a score that is 0.0, it might be read as False, so the following handles it
        def key_func(item):
            '''
            Sorting key for recommendations.

            - When ordering by "score", sorts by numeric score (missing -> -inf).
            - When ordering by "title", sorts case-insensitively by title.
            - Otherwise sorts by the given field when present, treating None as lowest.
            '''
            if order_by == "score":
                return item.get("score", float("-inf"))
            if order_by == "title":

                return (item.get("title") or "").casefold()
            val = item.get(order_by)
            # treat only None as missing (not 0.0)
            return val if val is not None else float("-inf")

        recommendations.sort(key=lambda x: (key_func(x), (x.get("title") or "").casefold()), reverse=reverse)

        offset = (page - 1) * size
        paginated = recommendations[offset : offset + size]

        return success("Recommendations generated successfully", data={
            "total_results": len(recommendations),
            "page": page,
            "size": size,
            "items": paginated
        })
    except ValueError as ve:
        logger.warning(f"Recommendation Skipped! (Likely due to no supplied manga): {ve}")
        return error("Recommendation Skipped!",str(ve))

    except Exception as e:
        logger.error(f"Failed to generate recommendations for user {user.id} on collection {collection_id}: {e}", exc_info=True)
        return error("Failed to generate recommendations")