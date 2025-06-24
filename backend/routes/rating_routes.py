from fastapi import APIRouter, Depends
import backend.schemas.rating as schemas
from backend.db.client_db import ClientDatabase
from utils.response import success, error
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rating", tags=['Rating'])

@router.post("/")
async def rate_manga(
        request: schemas.RateMangaRequest,
        db: ClientDatabase = Depends(lambda: get_db("user_write"))
):
    '''
    Allows a user to rate or update a rating for a specified manga.

    Returns:
        dict: Standardized success or error response.
    '''
    try:
        return await db.rate_manga(request.user_id, request.manga_id, float(request.score))
    except Exception:
        logger.error("Unexpected Error During Rating", exc_info=True)
        return error(message="Internal Server Error.", detail="Could not process rating.")

@router.get("/")
async def get_user_rating(
        user_id: int,
        manga_id: Optional[int] = None,
        db: ClientDatabase = Depends(lambda: get_db("user_write"))
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
        if manga_id:
            rating = await db.get_user_rating_for_manga(user_id, manga_id)
            if not rating:
                return error(message="Rating not Found", detail="No rating found for Manga. Either no rating or manga_id does not exist.")
            return success(message="Rating Found", data={"score" : float(rating.personal_rating)})
        
        else:
            ratings= await db.get_all_user_ratings(user_id)
            return success(message="All ratings retrieved", data={"ratings": [
                {"manga_id": r.manga_id, "score": float(r.personal_rating)} for r in ratings]})
        
    except Exception:
        logger.error("Unexpected Error During Rating", exc_info=True)
        return error(message="Internal Server Error.", detail="Could not process rating.")