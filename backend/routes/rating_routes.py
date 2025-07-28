from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.future import select
from backend.db.client_db import ClientDatabase
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.schemas.rating import RatingCreate, RatingRead
from backend.db.models.rating import Rating
from backend.db.models.user import User
from utils.response import success, error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ratings", tags=['Rating'])

@router.post("/", response_model=dict)
async def rate_manga(
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

        return success("Rating successfully submitted", data=validated) 
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Unexpected error during manga rating: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.put("/", response_model=dict)
async def update_rating(
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
            logger.warning(f"User {user.id} tried to updaste rating for manga {rating_data.manga_id} but no rating exists")
            return error("Rating not found", detail="You must create a rating before updating it")
        
        result = await db.rate_manga(
            user_id=user.id,
            manga_id=rating_data.manga_id,
            score=float(rating_data.personal_rating)
        )

        return result
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Unexpected error during manga rating update: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))
    
@router.delete("/{manga_id}", response_model=dict)
async def delete_rating(
    manga_id: int,
    db: ClientDatabase = Depends(get_user_write_db),
    user: User = Depends(current_user)
):
    try:
        logger.info(f"User {user.id} attempting to delete rating for manga {manga_id}.")

        existing = await db.get_user_rating_for_manga(user.id, manga_id)
        if not existing:
            logger.warning(f"User {user.id} attempted to delete rating for manga {manga_id}, but no rating exists.")
            return error("Rating not found", detail="You have not rated this manga")
        
        await db.session.delete(existing)
        await db.session.commit()

        logger.info(f"Successfully deleted rating for manga {manga_id} by user {user.id}")
        return success("Rating deleted successfully.", data={"manga_id": manga_id})
    
    except Exception as e:
        await db.session.rollback()
        logger.error(f"Error deleting rating for manga {manga_id}")


    
@router.get("/", response_model=dict)
async def get_user_ratings(
        manga_id: Optional[int] = Query(None),
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
        if manga_id:
            logger.info(f"Fetching rating for manga {manga_id} by user {user.id}")
            result = await db.session.execute(
                select(Rating).where(Rating.user_id == user.id, Rating.manga_id == manga_id)
            )
            rating = result.scalar_one_or_none()

            if not rating:
                return error("Rating not found", detail="User has not rated this manga.")

            validated = RatingRead.model_validate(rating)
            return success("Rating retrieved successfully", data=validated)
        
        else:
            logger.info(f"Fetching ALL ratings by user {user.id}")
            ratings = await db.get_all_user_ratings(user.id)
    
            if not ratings:
                return success("No ratings found", data=[])
            
            validated = [RatingRead.model_validate(r) for r in ratings]
            return success("Ratings retrieved successfully", data=validated)
        
    except Exception as e:
        logger.error(f"Unexpected error fetching rating for manga {manga_id} by user {user.id}: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))