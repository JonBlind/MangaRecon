from fastapi import APIRouter, Depends
from sqlalchemy.future import select
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.db.client_db import ClientDatabase
from backend.dependencies import get_manga_read_db
from backend.schemas.manga import GenreRead, TagRead, DemographicRead
from backend.utils.response import success, error
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Metadata"])

@router.get("/genres", response_model=dict)
async def get_all_genres(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all genres.")
        result = await db.session.execute(select(Genre))
        genres = result.scalars().all()

        validated = [GenreRead.model_validate(g) for g in genres]

        return success(message="Genres successfully retrieved", data=validated)
    except Exception as e:
        logger.error(f"Failed to get all genres: {e}")
        return error(message="Failed to retrieve genres", detail=str(e))
    
@router.get("/tags", response_model=dict)
async def get_all_tags(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all tags.")
        result = await db.session.execute(select(Tag))
        tags = result.scalars().all()

        validated = [TagRead.model_validate(t) for t in tags]

        return success(message="Tags successfully retrieved", data=validated)
    except Exception as e:
        logger.error(f"Failed to get all tags: {e}")
        return error(message="Failed to retrieve tags", detail=str(e))

@router.get("/demographics", response_model=dict)
async def get_all_demographics(db: ClientDatabase = Depends(get_manga_read_db)):
    try:
        logger.info("Retrieving all demographics.")
        result = await db.session.execute(select(Demographic))
        demographics = result.scalars().all()

        validated = [DemographicRead.model_validate(d) for d in demographics]

        return success(message="Demographics successfully retrieved", data=validated)
    except Exception as e:
        logger.error(f"Failed to get all demographics: {e}")
        return error(message="Failed to retrieve demographics", detail=str(e))