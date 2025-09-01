from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from backend.db.client_db import ClientDatabase
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
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    '''
    Allows a user to rate or update a rating for a specified manga.

    Returns:
        dict: Standardized success or error response.
    '''
    try:
        logger.info(f"User {user.id} submitting rating for manga {rating_data.manga_id} with score {rating_data.personal_rating}")
        result = await db.rate_manga(user_id=user.id, manga_id=rating_data.manga_id, personal_rating=float(rating_data.personal_rating))
        validated = RatingRead.model_validate(result)

        await invalidate_user_recommendations(db, user.id)
        return success("Rating successfully submitted", data=validated)
    
    except IntegrityError:
        await db.session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")

    except Exception as e:
        await db.session.rollback()
        logger.error(f"Unexpected error during manga rating: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.put("/", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def update_rating(
    request: Request,
    rating_data: RatingCreate,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
    ):
    '''
    Update the current user's existing rating.

    Returns:
        dict: Standardized success or error response.
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
            personal_rating=float(rating_data.personal_rating)
        )

        validated = RatingRead.model_validate(result)
        await invalidate_user_recommendations(db, user.id)

        return success("Rating updated successfully", data=validated)
    
    except IntegrityError:
        await db.session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Unexpected error during manga rating update: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.delete("/{manga_id}", response_model=dict)
@limiter.shared_limit("60/minute", scope="ratings-ip-min")
async def delete_rating(
    request: Request,
    manga_id: int,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"User {user.id} attempting to delete rating for manga {manga_id}.")

        existing = await db.get_user_rating_for_manga(user.id, manga_id)
        if not existing:
            logger.warning(f"User {user.id} attempted to delete rating for manga {manga_id}, but no rating exists.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
        
        await db.session.delete(existing)
        await db.session.commit()

        logger.info(f"Successfully deleted rating for manga {manga_id} by user {user.id}")
        await invalidate_user_recommendations(db, user.id)
        
        return success("Rating deleted successfully.", data={"manga_id": manga_id})
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Error deleting rating for manga {manga_id}: {e}")
        return error("Internal server error", detail=str(e))


    
@router.get("/", response_model=dict)
@limiter.limit("120/minute")
async def get_user_ratings(
    request: Request,
    manga_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: ClientDatabase = Depends(get_user_read_db),
    user: User = Depends(current_user)
):
    '''
    Get a user's manga rating(s). If a specific manga_id is provided, then only the rating for that ID returns. Otherwise, all of the user's ratings are returned.

    Args:
        manga_id (int, Optional): ID of manga to fetch a rating for. If left blank or None, will return all ratings. (Defaults to None.)

    Returns:
        dict: Standardized success or error response.
    '''
    try:
        if manga_id is not None:
            logger.info(f"Fetching rating for manga {manga_id} by user {user.id}")
            result = await db.session.execute(
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
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Rating.manga_id.asc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        rows = result.scalars().all()

        items = [RatingRead.model_validate(r) for r in rows]
        return success("Ratings retrieved successfully", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": items
        })

    except Exception as e:
        logger.error(f"Unexpected error fetching ratings for user {user.id}: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))