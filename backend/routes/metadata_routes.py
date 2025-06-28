from fastapi import APIRouter, Depends
from sqlalchemy.future import select
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.db.client_db import ClientDatabase
from backend.dependencies import get_manga_read_db
from backend.schemas.manga import GenreRead, TagRead, DemographicRead
from utils.response import success, error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Metadata"])

@router.get("/genre", response_model=dict)
async def get_all_genres(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all genres.")
        result = await db.session.execute(select(Genre))
        genres = result.scalars().all()

        return success(message="Genres successfully retrieved", data=genres)
    except Exception as e:
        logger.error(f"Failed to get all genres: {e}")
        return error(message="Failed to retrieve genres", detail=str(e))
    
@router.get("/tag", response_model=dict)
async def get_all_tags(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all tags.")
        result = await db.session.execute(select(Tag))
        tags = result.scalars().all()

        return success(message="Tags successfully retrieved", data=tags)
    except Exception as e:
        logger.error(f"Failed to get all tags: {e}")
        return error(message="Failed to retrieve tags", detail=str(e))

@router.get("/demographic", response_model=dict)
async def get_all_demographics(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all demographics.")
        result = await db.session.execute(select(Demographic))
        demographics = result.scalars().all()

        return success(message="Demographics successfully retrieved", data=demographics)
    except Exception as e:
        logger.error(f"Failed to get all demographics: {e}")
        return error(message="Failed to retrieve demographics", detail=str(e))