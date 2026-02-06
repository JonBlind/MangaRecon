from fastapi import APIRouter, Depends, Query, HTTPException, status, Request
from sqlalchemy import select
from backend.db.client_db import ClientReadDatabase
from backend.db.models.manga import Manga
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.db.models.join_tables import (
    manga_tag,
    manga_genre,
    manga_demographic
)
from backend.dependencies import get_manga_read_db, get_public_read_db
from backend.utils.ordering import MangaOrderField, OrderDirection, get_ordering_clause
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
    request: Request,
    manga_id: int,
    db: ClientReadDatabase = Depends(get_public_read_db)
):
    '''
    Retrieve a single manga by its identifier.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        manga_id (int): Identifier of the manga to retrieve.
        db (ClientDatabase): Manga-domain read database client.
    
    Returns:
        dict: Standardized response with the manga (MangaRead) or a 404 error if not found.
    '''
    
    try:
        logger.info(f"Fetching full manga metadata for manga {manga_id}")

        stmt = (
            select(
                Manga.manga_id,
                Manga.title,
                Manga.description,
                Manga.published_date,
                Manga.external_average_rating,
                Manga.average_rating,
                Manga.author_id,
                Manga.cover_image_url,
            )
            .where(Manga.manga_id == manga_id)
        )

        row = (await db.execute(stmt)).one_or_none()

        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manga not found")

        
        genre_result = await db.execute(
            select(Genre).join(manga_genre).where(manga_genre.c.manga_id == manga_id)
        )
        genres = [GenreRead.model_validate(g) for g in genre_result.scalars().all()]

        tag_result = await db.execute(
            select(Tag).join(manga_tag).where(manga_tag.c.manga_id == manga_id)
        )
        tags = [TagRead.model_validate(t) for t in tag_result.scalars().all()]

        demo_result = await db.execute(
            select(Demographic).join(manga_demographic).where(manga_demographic.c.manga_id == manga_id)
        )
        demographics = [DemographicRead.model_validate(d) for d in demo_result.scalars().all()]

        manga_response = MangaRead(
            manga_id=row.manga_id,
            title=row.title,
            description=row.description,
            published_date=row.published_date,
            external_average_rating=row.external_average_rating,
            average_rating=row.average_rating,
            author_id=row.author_id,
            genres=genres,
            tags=tags,
            demographics=demographics,
            cover_image_url = row.cover_image_url
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
    request: Request,
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
    order_dir: OrderDirection = Query("asc"),

    db: ClientReadDatabase = Depends(get_public_read_db)
):
    '''
    List and filter manga with optional genre, tag, and demographic criteria, plus title search.

    Args:
        request (Request): FastAPI request (required by rate limiting).
        genre_ids (Optional[List[int]]): Only include manga that have any of these genres.
        exclude_genres (Optional[List[int]]): Exclude manga that have any of these genres.
        tag_ids (Optional[List[int]]): Only include manga that have any of these tags.
        exclude_tags (Optional[List[int]]): Exclude manga that have any of these tags.
        demo_ids (Optional[List[int]]): Only include manga that have any of these demographics.
        exclude_demos (Optional[List[int]]): Exclude manga that have any of these demographics.
        title (Optional[str]): Case-insensitive substring to match on title.
        page (int): 1-based page number.
        size (int): Page size (1 - 100).
        order_by (MangaOrderField): Field to order the results by.
        order_dir (OrderDirection): Sort direction ("asc" or "desc").
        db (ClientDatabase): Manga-domain read database client.

    Returns:
        dict: Standardized response with total_results, page, size, and items (MangaListItem).
    '''
    try:
        logger.info(f"Filtering manga - page={page}, size={size}, order_by={order_by}, order_dir={order_dir}")
        offset = (page - 1) * size

        stmt = select(
            Manga.manga_id,
            Manga.title,
            Manga.description,
            Manga.cover_image_url,
            Manga.average_rating,
            Manga.external_average_rating,
        ).distinct()

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
        total = (await db.execute(count_stmt)).scalar_one()

        # Order
        stmt = stmt.order_by(get_ordering_clause(order_by, order_dir))

        # Paginate
        stmt = stmt.offset(offset).limit(size)

        result = await db.execute(stmt)
        rows = result.all()

        items = [
            MangaListItem(
                manga_id=r.manga_id,
                title=r.title,
                description=r.description,
                cover_image_url=r.cover_image_url,
                average_rating=r.average_rating,
                external_average_rating=r.external_average_rating,
                genres=[],
            )
            for r in rows
        ]

        manga_ids_page = [r.manga_id for r in rows]

        # Bulk-fetch genres for the page
        if manga_ids_page:
            genre_rows = (
                await db.execute(
                    select(
                        manga_genre.c.manga_id.label("manga_id"),
                        Genre.genre_id.label("genre_id"),
                        Genre.genre_name.label("genre_name"),
                    )
                    .select_from(manga_genre)
                    .join(Genre, Genre.genre_id == manga_genre.c.genre_id)
                    .where(manga_genre.c.manga_id.in_(manga_ids_page))
                    .order_by(manga_genre.c.manga_id, Genre.genre_name)
                )
            ).all()

            genre_map: dict[int, list[GenreRead]] = {}
            for gr in genre_rows:
                genre_map.setdefault(int(gr.manga_id), []).append(
                    GenreRead(genre_id=int(gr.genre_id), genre_name=gr.genre_name)
                )

            # Attach genres to each MangaListItem
            for it in items:
                it.genres = genre_map.get(it.manga_id, [])

        return success("Filtered manga retrieved successfully", data={
            "total_results": total,
            "page": page,
            "size": size,
            "items": items
        })

    except Exception as e:
        logger.error(f"Error filtering manga list: {e}", exc_info=True)
        return error("Failed to retrieve manga list", detail=str(e))