from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.future import select
from backend.db.client_db import ClientDatabase
from backend.db.models.manga import Manga
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.auth.dependencies import current_active_verified_user as current_user
from backend.db.models.join_tables import (
    manga_tag,
    manga_genre,
    manga_demographic
)
from backend.dependencies import get_manga_read_db
from backend.utils.ordering import MangaOrderField, MangaOrderDirection, get_ordering_clause
from backend.schemas.manga import MangaRead, GenreRead, TagRead, DemographicRead, MangaListItem
from backend.utils.response import success, error
from backend.utils.rate_limit import limiter
from typing import List, Optional
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mangas", tags=["Mangas"])

@router.get("/{manga_id}", response_model=dict)
@limiter.shared_limit("240/minute", scope="manga-detail-ip-min")
@limiter.shared_limit("10000/day", scope="manga-detail-ip-day") 
async def get_manga_by_id(
    manga_id: int,
    db: ClientDatabase = Depends(get_manga_read_db)
):
    """
    Retrieve full metadata for a specific manga including genres, tags, and demographics.

    Returns:
        dict: Standardized success or error response.
    """
    
    try:
        logger.info(f"Fetching full manga metadata for manga {manga_id}")

        result = await db.session.execute(select(Manga).where(Manga.manga_id == manga_id))

        manga = result.scalar_one_or_none()

        if not manga:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")
        
        genre_result = await db.session.execute(
            select(Genre).join(manga_genre).where(manga_genre.c.manga_id == manga_id)
        )
        genres = [GenreRead.model_validate(g) for g in genre_result.scalars().all()]

        tag_result = await db.session.execute(
            select(Tag).join(manga_tag).where(manga_tag.c.manga_id == manga_id)
        )
        tags = [TagRead.model_validate(t) for t in tag_result.scalars().all()]

        demo_result = await db.session.execute(
            select(Demographic).join(manga_demographic).where(manga_demographic.c.manga_id == manga_id)
        )
        demographics = [DemographicRead.model_validate(d) for d in demo_result.scalars().all()]

        manga_response = MangaRead(
            manga_id=manga.manga_id,
            title=manga.title,
            description=manga.description,
            published_date=manga.published_date,
            external_average_rating=manga.external_average_rating,
            average_rating=manga.average_rating,
            author_id=manga.author_id,
            genres=genres,
            tags=tags,
            demographics=demographics,
            cover_image_url = manga.cover_image_url
        )

        return success("Manga retrieved successfully", data=manga_response)
    except Exception as e:
        logger.error(f"Error retrieving manga {manga_id}: {e}", exc_info=True)
        return error("Failed to retrieve manga", detail=str(e))
    
@router.get("/", response_model=dict)
@limiter.shared_limit("120/minute", scope="search-ip-min")
@limiter.shared_limit("3000/hour",   scope="search-ip-hour")
@limiter.shared_limit("20000/day",   scope="search-ip-day")  
async def filter_manga(
    genre_ids: Optional[List[int]] = Query(default=None),
    exclude_genres: Optional[List[int]] = Query(default=None),
    tag_ids: Optional[List[int]] = Query(default=None),
    exclude_tags: Optional[List[int]] = Query(default=None),
    demo_ids: Optional[List[int]] = Query(default=None),
    exclude_demos: Optional[List[int]] = Query(default=None),
    title: Optional[str] = Query(default=None),

    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),

    order_by: MangaOrderField = Query("title"),
    order_dir: MangaOrderDirection = Query("asc"),

    db: ClientDatabase = Depends(get_manga_read_db)
):
    try:
        logger.info(f"Filtering manga - page={page}, size={size}, order_by={order_by}, order_dir={order_dir}")
        offset = (page - 1) * size

        stmt = select(Manga).distinct()

        # Filters
        if title:
            stmt = stmt.where(Manga.title.ilike(f"%{title}%"))

        if genre_ids:
            stmt = stmt.join(manga_genre).where(manga_genre.c.genre_id.in_(genre_ids))

        if exclude_genres:
            stmt = stmt.where(~Manga.manga_id.in_(
                select(manga_genre.c.manga_id).where(manga_genre.c.genre_id.in_(exclude_genres))
            ))

        if tag_ids:
            stmt = stmt.join(manga_tag).where(manga_tag.c.tag_id.in_(tag_ids))

        if exclude_tags:
            stmt = stmt.where(~Manga.manga_id.in_(
                select(manga_tag.c.manga_id).where(manga_tag.c.tag_id.in_(exclude_tags))
            ))

        if demo_ids:
            stmt = stmt.join(manga_demographic).where(manga_demographic.c.demographic_id.in_(demo_ids))

        if exclude_demos:
            stmt = stmt.where(~Manga.manga_id.in_(
                select(manga_demographic.c.manga_id).where(manga_demographic.c.demographic_id.in_(exclude_demos))
            ))

        # Count
        count_stmt = stmt.with_only_columns(func.count(func.distinct(Manga.manga_id))).order_by(None)
        total = (await db.session.execute(count_stmt)).scalar_one()

        # Order
        stmt = stmt.order_by(get_ordering_clause(order_by, order_dir))

        # Paginate
        stmt = stmt.offset(offset).limit(size)

        result = await db.session.execute(stmt)
        manga_list = result.scalars().all()

        validated = [MangaListItem.model_validate(manga) for manga in manga_list]

        return success("Filtered manga retrieved successfully", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": validated
        })

    except Exception as e:
        logger.error(f"Error filtering manga list: {e}", exc_info=True)
        return error("Failed to retrieve manga list", detail=str(e))