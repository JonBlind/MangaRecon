from fastapi import APIRouter, Depends, Query, Request
from typing import Optional
import logging

from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_user as current_user
from backend.schemas.rating import RatingCreate
from backend.db.models.user import User
from backend.utils.response import success
from backend.utils.rate_limit import limiter

from backend.services.rating_service import (
    create_or_update_rating,
    update_existing_rating,
    delete_user_rating_for_manga,
    get_user_ratings_page,
    get_single_user_rating,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=["Ratings"])


@router.post("", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def rate_manga(
    request: Request,
    rating_data: RatingCreate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    """
    Create or update a personal rating for a manga by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        rating_data (RatingCreate): Payload containing manga_id and personal_rating.
        db (ClientWriteDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the upserted rating.
    """
    logger.info(
        "User %s submitting rating for manga %s with score %s",
        user.id,
        rating_data.manga_id,
        rating_data.personal_rating,
    )
    validated = await create_or_update_rating(user_id=user.id, payload=rating_data, user_db=db)
    return success("Rating successfully submitted", data=validated)


@router.put("", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def update_rating(
    request: Request,
    rating_data: RatingCreate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    """
    Update an existing personal rating for a manga by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        rating_data (RatingCreate): Payload containing manga_id and personal_rating.
        db (ClientWriteDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the updated rating or 404 if not found.
    """
    logger.info(
        "User %s attempting to update rating for manga %s with score %s",
        user.id,
        rating_data.manga_id,
        rating_data.personal_rating,
    )
    validated = await update_existing_rating(user_id=user.id, payload=rating_data, user_db=db)
    return success("Rating updated successfully", data=validated)


@router.delete("/{manga_id}", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def delete_rating(
    request: Request,
    manga_id: int,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user),
):
    """
    Delete the current user's rating for a manga.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        manga_id (int): Identifier of the manga whose rating will be removed.
        db (ClientWriteDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response confirming deletion.
    """
    logger.info("User %s attempting to delete rating for manga %s.", user.id, manga_id)
    out = await delete_user_rating_for_manga(user_id=user.id, manga_id=manga_id, user_db=db)
    return success("Rating deleted successfully.", data=out)


@router.get("", response_model=dict)
@limiter.limit("120/minute")
async def get_user_ratings(
    request: Request,
    manga_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user),
):
    """
    List the current user's ratings (optionally filtered by manga) with pagination.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        manga_id (Optional[int]): If provided, only return the rating for this manga.
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        db (ClientReadDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with ratings (single or paginated list).
    """
    if manga_id is not None:
        logger.info("Fetching rating for manga %s by user %s", manga_id, user.id)
        validated = await get_single_user_rating(user_id=user.id, manga_id=manga_id, user_db=db)
        return success("Rating retrieved successfully", data=validated)

    logger.info("Fetching paginated ratings for user %s page=%s size=%s", user.id, page, size)
    data = await get_user_ratings_page(user_id=user.id, page=page, size=size, user_db=db)
    return success("Ratings retrieved successfully", data=data)