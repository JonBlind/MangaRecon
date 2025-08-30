from fastapi import APIRouter, Depends, Query
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
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    db: ClientDatabase = Depends(get_manga_read_db)
):
    try:
        logger.info(f"Retrieving genres page={page} size={size}")
        offset = (page - 1) * size

        base = select(Genre)
        count_stmt = base.with_only_columns(func.count(Genre.genre_id)).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Genre.genre_id.asc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        genres = result.scalars().all()

        validated = [GenreRead.model_validate(g) for g in genres]
        return success(message="Genres successfully retrieved", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": validated
        })
    except Exception as e:
        logger.error(f"Failed to get all genres: {e}", exc_info=True)
        return error(message="Failed to retrieve genres", detail=str(e))
    
@router.get("/tags", response_model=dict)
@limiter.shared_limit("240/minute", scope=S_META_MIN)
@limiter.shared_limit("5000/hour",  scope=S_META_HOUR)
@limiter.shared_limit("50000/day",  scope=S_META_DAY)
async def get_all_tags(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    db: ClientDatabase = Depends(get_manga_read_db)
):
    try:
        logger.info(f"Retrieving tags page={page} size={size}")
        offset = (page - 1) * size

        base = select(Tag)
        count_stmt = base.with_only_columns(func.count(Tag.tag_id)).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Tag.tag_id.asc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        tags = result.scalars().all()

        validated = [TagRead.model_validate(t) for t in tags]
        return success(message="Tags successfully retrieved", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": validated
        })
    except Exception as e:
        logger.error(f"Failed to get all tags: {e}", exc_info=True)
        return error(message="Failed to retrieve tags", detail=str(e))

@router.get("/demographics", response_model=dict)
@limiter.shared_limit("240/minute", scope=S_META_MIN)
@limiter.shared_limit("5000/hour",  scope=S_META_HOUR)
@limiter.shared_limit("50000/day",  scope=S_META_DAY)
async def get_all_demographics(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    db: ClientDatabase = Depends(get_manga_read_db)
):
    try:
        logger.info(f"Retrieving demographics page={page} size={size}")
        offset = (page - 1) * size

        base = select(Demographic)
        count_stmt = base.with_only_columns(func.count(Demographic.demographic_id)).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Demographic.demographic_id.asc()).offset(offset).limit(size)
        result = await db.session.execute(stmt)
        demographics = result.scalars().all()

        validated = [DemographicRead.model_validate(d) for d in demographics]
        return success(message="Demographics successfully retrieved", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": validated
        })
    except Exception as e:
        logger.error(f"Failed to get all demographics: {e}", exc_info=True)
        return error(message="Failed to retrieve demographics", detail=str(e))