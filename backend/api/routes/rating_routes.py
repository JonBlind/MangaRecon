from fastapi import APIRouter, Depends
import backend.schemas.rating as schemas
from backend.api.client_db import ClientDatabase
from backend.api.dependencies import get_db
from utils.response import success, error
from utils.auth_utils import hash_password
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