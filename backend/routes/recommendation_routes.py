from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.db.models.user import User
from backend.utils.ordering import MangaOrderField, MangaOrderDirection, get_ordering_clause
from backend.dependencies import get_user_read_db
from backend.cache.redis import redis_cache
from backend.utils.response import success, error
from recommendation.generator import generate_recommendations
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

@router.get("/{collection_id}", response_model=dict)
async def get_recommendations_for_collection(
    collection_id: int,
    order_by: MangaOrderField = Query("score"),
    order_dir: MangaOrderDirection = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    """
    Returns paginated, ordered manga recommendations for a specific user collection.
    """
    logger.info(f"Generating recommendations for collection: {collection_id}")
    try:
        cache_key = f"recommendations:{user.id}:{collection_id}"
        recommendations = await redis_cache.get(cache_key)
        
        if recommendations is None:
            recommendations = await generate_recommendations(user.id, collection_id, session)
            await redis_cache.set(cache_key, recommendations)

        reverse = (order_dir == "desc")

        recommendations.sort(
            key=lambda x: (
                x["score"] if order_by == "score"
                else x.get(order_by) or "" if order_by == "title"
                else x.get(order_by) or -float("inf")
            ),
            reverse=reverse
        )

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