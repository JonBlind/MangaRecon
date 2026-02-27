'''
FastAPI routes for generating collection-based recommendations.

This router exposes ``GET /recommendations/{collection_id}`` which:
  1) Verifies the collection belongs to the authenticated (active, verified) user.
  2) Attempts to return a cached recommendation set from Redis.
  3) On cache miss, calls the recommendation generator and stores the result.
  4) Applies sorting and pagination over the in-memory result.
Returned payloads use the project-wide response envelope.
'''

from fastapi import APIRouter, Depends, Query, Request

from backend.auth.dependencies import current_active_user as current_user
from backend.db.models.user import User
from backend.db.client_db import ClientReadDatabase
from backend.utils.ordering import OrderDirection, RecommendationOrderField
from backend.dependencies import get_user_read_db, get_public_read_db
from backend.cache.redis import get_redis_cache
from backend.utils.response import success
from backend.utils.rate_limit import limiter
from backend.schemas.recommendation import RecommendationQueryListRequest
from backend.services.recommendation_service import (
    get_recommendations_for_collection_page,
    get_recommendations_for_query_list_page,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/{collection_id}", response_model=dict)
@limiter.shared_limit("10/minute", scope="recs-ip-min")
@limiter.shared_limit("500/day", scope="recs-ip-day")
async def get_recommendations_for_collection(
    request: Request,
    collection_id: int,
    order_by: RecommendationOrderField = Query("score"),
    order_dir: OrderDirection = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
    redis_cache=Depends(get_redis_cache),
):
    '''
    Return paginated, ordered recommendations for the given collection.
    '''
    logger.info("Generating recommendations for collection: %s", collection_id)
    data = await get_recommendations_for_collection_page(
        user_id=user.id,
        collection_id=collection_id,
        order_by=order_by,
        order_dir=order_dir,
        page=page,
        size=size,
        user_db=db,
        redis_cache=redis_cache,
    )
    return success("Recommendations generated successfully", data=data)


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
    '''
    data = await get_recommendations_for_query_list_page(
        manga_ids=payload.manga_ids,
        order_by=order_by,
        order_dir=order_dir,
        page=page,
        size=size,
        db=db,
    )
    return success("Recommendations generated successfully", data=data)