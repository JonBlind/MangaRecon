from fastapi import APIRouter, Depends
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

@router.post("/")
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
    
@router.get("/")
async def get_user_rating_for_manga(
        manga_id: int,
        db: ClientDatabase = Depends(get_user_read_db),
        user: User = Depends(current_user)
):
    '''
    Get a urser's manga rating(s). If a specific manga_id is provided, then only the rating for that ID returns. Otherwise, all of the user's ratings are returned.

    Args:
        user_id (int): ID of user to fetch ratings for.
        manga_id (int, Optional): ID of manga to fetch a rating for. If left blank or None, will return all ratings. (Defaults to None.)

    Returns:
        dict: Standardized success or error response.
    '''
    try:
        logger.info(f"Fetching rating for manga {manga_id} by user {user.id}")
        result = await db.session.execute(
            select(Rating).where(Rating.user_id == user.id, Rating.manga_id == manga_id)
        )
        rating = result.scalar_one_or_none()

        if not rating:
            return error("Rating not found", detail="User has not rated this manga.")

        validated = RatingRead.model_validate(rating)
        return success("Rating retrieved successfully", data=validated)

    except Exception as e:
        logger.error(f"Unexpected error fetching rating for manga {manga_id} by user {user.id}: {e}", exc_info=True)
        return error("Internal server error", detail=str(e))