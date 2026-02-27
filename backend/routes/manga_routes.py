from fastapi import APIRouter, Depends, Query, Request
from typing import List, Optional
from backend.db.client_db import ClientReadDatabase
from backend.dependencies import get_public_read_db
from backend.utils.ordering import MangaOrderField, OrderDirection
from backend.utils.response import success
from backend.utils.rate_limit import limiter
from backend.services.manga_service import get_manga_detail, filter_manga_page
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mangas", tags=["Mangas"])


@router.get("/{manga_id}", response_model=dict)
@limiter.shared_limit("240/minute", scope="manga-detail-ip-min")
@limiter.shared_limit("10000/day", scope="manga-detail-ip-day")
async def get_manga_by_id(
    request: Request,
    manga_id: int,
    db: ClientReadDatabase = Depends(get_public_read_db),
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
        logger.info("Fetching full manga metadata for manga %s", manga_id)
        manga = await get_manga_detail(manga_id=manga_id, db=db)
        return success("Manga retrieved successfully", data=manga)

    except Exception as e:
        logger.error("Error retrieving manga %s: %s", manga_id, e, exc_info=True)
        raise


@router.get("/", response_model=dict)
@limiter.shared_limit("120/minute", scope="search-ip-min")
@limiter.shared_limit("3000/hour", scope="search-ip-hour")
@limiter.shared_limit("20000/day", scope="search-ip-day")
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
    db: ClientReadDatabase = Depends(get_public_read_db),
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
        logger.info("Filtering manga page=%s size=%s order_by=%s order_dir=%s", page, size, order_by, order_dir)

        data = await filter_manga_page(
            genre_ids=genre_ids,
            exclude_genres=exclude_genres,
            tag_ids=tag_ids,
            exclude_tags=exclude_tags,
            demo_ids=demo_ids,
            exclude_demos=exclude_demos,
            title=title,
            page=page,
            size=size,
            order_by=order_by,
            order_dir=order_dir,
            db=db,
        )

        return success("Filtered manga retrieved successfully", data=data)

    except Exception as e:
        logger.error("Error filtering manga list: %s", e, exc_info=True)
        raise