from __future__ import annotations

from typing import List, Optional

from backend.db.client_db import ClientReadDatabase
from backend.repositories.manga_repo import (
    fetch_manga_core_by_id,
    fetch_manga_genres,
    fetch_manga_tags,
    fetch_manga_demographics,
    build_filter_stmt,
    count_filtered_manga,
    fetch_filtered_manga_page,
    fetch_genres_for_manga_ids,
)
from backend.schemas.manga import MangaRead, GenreRead, TagRead, DemographicRead, MangaListItem
from backend.utils.ordering import MangaOrderField, OrderDirection
from backend.utils.domain_exceptions import NotFoundError

async def get_manga_detail(*, manga_id: int, db: ClientReadDatabase) -> MangaRead:
    row = await fetch_manga_core_by_id(db, manga_id=manga_id)
    if not row:
        raise NotFoundError(code="MANGA_NOT_FOUND", message="Manga not found.")

    genres = [GenreRead.model_validate(g) for g in await fetch_manga_genres(db, manga_id=manga_id)]
    tags = [TagRead.model_validate(t) for t in await fetch_manga_tags(db, manga_id=manga_id)]
    demographics = [DemographicRead.model_validate(d) for d in await fetch_manga_demographics(db, manga_id=manga_id)]

    return MangaRead(
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
        cover_image_url=row.cover_image_url,
    )


async def filter_manga_page(
    *,
    genre_ids: Optional[List[int]],
    exclude_genres: Optional[List[int]],
    tag_ids: Optional[List[int]],
    exclude_tags: Optional[List[int]],
    demo_ids: Optional[List[int]],
    exclude_demos: Optional[List[int]],
    title: Optional[str],
    page: int,
    size: int,
    order_by: MangaOrderField,
    order_dir: OrderDirection,
    db: ClientReadDatabase,
) -> dict:
    offset = (page - 1) * size

    stmt = build_filter_stmt(
        genre_ids=genre_ids,
        exclude_genres=exclude_genres,
        tag_ids=tag_ids,
        exclude_tags=exclude_tags,
        demo_ids=demo_ids,
        exclude_demos=exclude_demos,
        title=title,
    )

    total = await count_filtered_manga(db, stmt=stmt)
    rows = await fetch_filtered_manga_page(
        db,
        stmt=stmt,
        offset=offset,
        limit=size,
        order_by=order_by,
        order_dir=order_dir,
    )

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

    if manga_ids_page:
        genre_rows = await fetch_genres_for_manga_ids(db, manga_ids=manga_ids_page)

        genre_map: dict[int, list[GenreRead]] = {}
        for gr in genre_rows:
            genre_map.setdefault(int(gr.manga_id), []).append(
                GenreRead(genre_id=int(gr.genre_id), genre_name=gr.genre_name)
            )

        for it in items:
            it.genres = genre_map.get(it.manga_id, [])

    return {"total_results": total, "page": page, "size": size, "items": items}
