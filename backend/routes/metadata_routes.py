from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func
from sqlalchemy import select
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.db.client_db import ClientDatabase
from backend.dependencies import get_manga_read_db
from backend.schemas.manga import GenreRead, TagRead, DemographicRead
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metadata", tags=["Metadata"])

S_META_MIN   = "metadata-ip-min"
S_META_HOUR  = "metadata-ip-hour"
S_META_DAY   = "metadata-ip-day"

@router.get("/genres", response_model=dict)
@limiter.shared_limit("240/minute", scope=S_META_MIN)
@limiter.shared_limit("5000/hour",  scope=S_META_HOUR)
@limiter.shared_limit("50000/day",  scope=S_META_DAY)
async def get_all_genres(
    request: Request,
    db: ClientDatabase = Depends(get_manga_read_db)
):
    '''
    Return all available genres.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        db (ClientDatabase): Manga-domain read database client.

    Returns:
        dict: Standardized 'Response' with list of Genres and total_results (int).
    '''
    try:
        logger.info("Retrieving all genres (no pagination)")
        stmt = select(Genre).order_by(Genre.genre_id.asc())
        result = await db.session.execute(stmt)
        genres = result.scalars().all()
        items = [GenreRead.model_validate(g) for g in genres]
        return success(message="Genres successfully retrieved", data={
            "total_results": len(items),
            "items": items
        })
    except Exception as e:
        logger.error(f"Failed to get all genres: {e}", exc_info=True)
        return error(message="Failed to retrieve genres", detail=str(e))
    
@router.get("/tags", response_model=dict)
@limiter.shared_limit("240/minute", scope=S_META_MIN)
@limiter.shared_limit("5000/hour",  scope=S_META_HOUR)
@limiter.shared_limit("50000/day",  scope=S_META_DAY)
async def get_all_tags(
    request: Request,
    db: ClientDatabase = Depends(get_manga_read_db)
):
    '''
    Return all available tags.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        db (ClientDatabase): Manga-domain read database client.

    Returns:
        dict: Standardized 'Response' with list of Tags and total_results (int).
    '''
    try:
        logger.info("Retrieving all tags (no pagination)")
        stmt = select(Tag).order_by(Tag.tag_id.asc())
        result = await db.session.execute(stmt)
        tags = result.scalars().all()
        items = [TagRead.model_validate(t) for t in tags]
        return success(message="Tags successfully retrieved", data={
            "total_results": len(items),
            "items": items
        })
    except Exception as e:
        logger.error(f"Failed to get all tags: {e}", exc_info=True)
        return error(message="Failed to retrieve tags", detail=str(e))

@router.get("/demographics", response_model=dict)
@limiter.shared_limit("240/minute", scope=S_META_MIN)
@limiter.shared_limit("5000/hour",  scope=S_META_HOUR)
@limiter.shared_limit("50000/day",  scope=S_META_DAY)
async def get_all_demographics(
    request: Request,
    db: ClientDatabase = Depends(get_manga_read_db)
):
    '''
    Return all available demographics.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        db (ClientDatabase): Manga-domain read database client.

    Returns:
        dict: Standardized 'Response' with list of Demographics and total_results (int).
    '''
    try:
        logger.info("Retrieving all demographics (no pagination)")
        stmt = select(Demographic).order_by(Demographic.demographic_id.asc())
        result = await db.session.execute(stmt)
        demographics = result.scalars().all()
        items = [DemographicRead.model_validate(d) for d in demographics]
        return success(message="Demographics successfully retrieved", data={
            "total_results": len(items),
            "items": items
        })
    except Exception as e:
        logger.error(f"Failed to get all demographics: {e}", exc_info=True)
        return error(message="Failed to retrieve demographics", detail=str(e))