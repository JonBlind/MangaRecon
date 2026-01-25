from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.schemas.rating import RatingCreate, RatingRead
from backend.db.models.rating import Rating
from backend.db.models.user import User
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
from backend.cache.invalidation import invalidate_user_recommendations
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=['Ratings'])

@router.post("/", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def rate_manga(
    request: Request,
    rating_data: RatingCreate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    '''
    Create or update a personal rating for a manga owned by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        rating_data (RatingCreate): Payload containing the target manga ID and the personal rating value.
        db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the upserted rating (RatingRead) or an error detail.
    '''
    try:
        logger.info(f"User {user.id} submitting rating for manga {rating_data.manga_id} with score {rating_data.personal_rating}")
        result = await db.rate_manga(user_id=user.id, manga_id=rating_data.manga_id, score=float(rating_data.personal_rating))
        validated = RatingRead.model_validate(result)

        await invalidate_user_recommendations(db, user.id)
        return success("Rating successfully submitted", data=validated)
    
    except HTTPException:
        raise
    
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")

    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error during manga rating: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.put("/", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def update_rating(
    request: Request,
    rating_data: RatingCreate,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
    ):
    '''
    Update an existing personal rating for a manga owned by the current user.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        rating_data (RatingCreate): Payload containing the target manga ID and the new personal rating value.
        db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with the updated rating (RatingRead) or a not-found/error detail.
    '''
    try:
        logger.info(f"User {user.id} attempting to update rating for manga {rating_data.manga_id} with score {rating_data.personal_rating}")
        existing = await db.get_user_rating_for_manga(user.id, rating_data.manga_id)

        if not existing:
            logger.warning(f"User {user.id} tried to update rating for manga {rating_data.manga_id} but no rating exists")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
        
        result = await db.rate_manga(
            user_id=user.id,
            manga_id=rating_data.manga_id,
            score=float(rating_data.personal_rating)
        )

        validated = RatingRead.model_validate(result)
        await invalidate_user_recommendations(db, user.id)

        return success("Rating updated successfully", data=validated)
    
    except HTTPException:
        raise
    
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Unexpected error during manga rating update: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.delete("/{manga_id}", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def delete_rating(
    request: Request,
    manga_id: int,
    db: ClientWriteDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    '''
    Delete the authenticated user's rating for a specific manga and invalidate cached recommendations.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        manga_id (int): Identifier of the manga whose rating will be removed.
        db (ClientDatabase): User-domain write database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response confirming deletion and echoing the manga_id.
    '''
    try:
        logger.info(f"User {user.id} attempting to delete rating for manga {manga_id}.")

        existing = await db.get_user_rating_for_manga(user.id, manga_id)
        if not existing:
            logger.warning(f"User {user.id} attempted to delete rating for manga {manga_id}, but no rating exists.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
        
        await db.delete(existing)
        await db.commit()

        logger.info(f"Successfully deleted rating for manga {manga_id} by user {user.id}")
        await invalidate_user_recommendations(db, user.id)
        
        return success("Rating deleted successfully.", data={"manga_id": manga_id})
    
    except HTTPException:
        raise
    
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting rating for manga {manga_id}: {e}")
        return error("Internal server error", detail=str(e))


    
@router.get("/", response_model=dict)
@limiter.limit("120/minute")
async def get_user_ratings(
    request: Request,
    manga_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientReadDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    '''
    List the authenticated user's ratings (optionally filtered by manga) with pagination.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        manga_id (Optional[int]): If provided, only return the rating for this manga.
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        db (ClientDatabase): User-domain read database client.
        user (User): Currently authenticated, active, verified user.

    Returns:
        dict: Standardized response with total_results, page, size, and items (RatingRead).
    '''
    try:
        if manga_id is not None:
            logger.info(f"Fetching rating for manga {manga_id} by user {user.id}")
            result = await db.execute(
                select(Rating).where(Rating.user_id == user.id, Rating.manga_id == manga_id)
            )
            rating = result.scalar_one_or_none()

            if not rating:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
            
            validated = RatingRead.model_validate(rating)
            return success("Rating retrieved successfully", data=validated)

        # list mode
        logger.info(f"Fetching paginated ratings for user {user.id} page={page} size={size}")
        offset = (page - 1) * size

        base = select(Rating).where(Rating.user_id == user.id)
        count_stmt = base.with_only_columns(func.count()).order_by(None)
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Rating.manga_id.asc()).offset(offset).limit(size)
        result = await db.execute(stmt)
        rows = result.scalars().all()

        items = [RatingRead.model_validate(r) for r in rows]
        return success("Ratings retrieved successfully", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": items
        })
    
    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error fetching ratings for user {user.id}: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))