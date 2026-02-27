from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select

from backend.db.client_db import ClientReadDatabase
from backend.db.models.manga import Manga
from backend.db.models.genre import Genre
from backend.db.models.tag import Tag
from backend.db.models.demographics import Demographic
from backend.db.models.join_tables import manga_genre, manga_tag, manga_demographic
from backend.utils.ordering import MangaOrderField, OrderDirection, get_ordering_clause


async def fetch_manga_core_by_id(db: ClientReadDatabase, *, manga_id: int):
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
    return (await db.execute(stmt)).one_or_none()


async def fetch_manga_genres(db: ClientReadDatabase, *, manga_id: int):
    res = await db.execute(
        select(Genre).join(manga_genre).where(manga_genre.c.manga_id == manga_id)
    )
    return res.scalars().all()


async def fetch_manga_tags(db: ClientReadDatabase, *, manga_id: int):
    res = await db.execute(
        select(Tag).join(manga_tag).where(manga_tag.c.manga_id == manga_id)
    )
    return res.scalars().all()


async def fetch_manga_demographics(db: ClientReadDatabase, *, manga_id: int):
    res = await db.execute(
        select(Demographic).join(manga_demographic).where(manga_demographic.c.manga_id == manga_id)
    )
    return res.scalars().all()


def build_filter_stmt(
    *,
    genre_ids: Optional[list[int]],
    exclude_genres: Optional[list[int]],
    tag_ids: Optional[list[int]],
    exclude_tags: Optional[list[int]],
    demo_ids: Optional[list[int]],
    exclude_demos: Optional[list[int]],
    title: Optional[str],
):
    stmt = (
        select(
            Manga.manga_id,
            Manga.title,
            Manga.description,
            Manga.cover_image_url,
            Manga.average_rating,
            Manga.external_average_rating,
        )
        .distinct()
    )

    if title:
        stmt = stmt.where(Manga.title.ilike(f"%{title}%"))

    if genre_ids:
        stmt = stmt.join(manga_genre).where(manga_genre.c.genre_id.in_(genre_ids))

    if exclude_genres:
        stmt = stmt.where(
            ~Manga.manga_id.in_(
                select(manga_genre.c.manga_id).where(manga_genre.c.genre_id.in_(exclude_genres))
            )
        )

    if tag_ids:
        stmt = stmt.join(manga_tag).where(manga_tag.c.tag_id.in_(tag_ids))

    if exclude_tags:
        stmt = stmt.where(
            ~Manga.manga_id.in_(
                select(manga_tag.c.manga_id).where(manga_tag.c.tag_id.in_(exclude_tags))
            )
        )

    if demo_ids:
        stmt = stmt.join(manga_demographic).where(manga_demographic.c.demographic_id.in_(demo_ids))

    if exclude_demos:
        stmt = stmt.where(
            ~Manga.manga_id.in_(
                select(manga_demographic.c.manga_id).where(manga_demographic.c.demographic_id.in_(exclude_demos))
            )
        )

    return stmt


async def count_filtered_manga(db: ClientReadDatabase, *, stmt):
    count_stmt = stmt.with_only_columns(func.count(func.distinct(Manga.manga_id))).order_by(None)
    return (await db.execute(count_stmt)).scalar_one()


async def fetch_filtered_manga_page(
    db: ClientReadDatabase,
    *,
    stmt,
    offset: int,
    limit: int,
    order_by: MangaOrderField,
    order_dir: OrderDirection,
):
    stmt = stmt.order_by(get_ordering_clause(order_by, order_dir)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    return res.all()


async def fetch_genres_for_manga_ids(db: ClientReadDatabase, *, manga_ids: Sequence[int]):
    if not manga_ids:
        return []

    res = await db.execute(
        select(
            manga_genre.c.manga_id.label("manga_id"),
            Genre.genre_id.label("genre_id"),
            Genre.genre_name.label("genre_name"),
        )
        .select_from(manga_genre)
        .join(Genre, Genre.genre_id == manga_genre.c.genre_id)
        .where(manga_genre.c.manga_id.in_(list(manga_ids)))
        .order_by(manga_genre.c.manga_id, Genre.genre_name)
    )
    return res.all()

async def fetch_manga_list_base(
    db: ClientReadDatabase,
    *,
    manga_ids: Sequence[int],
) -> dict[int, dict]:
    """
    Fetch minimal list-item fields for a set of manga_ids and return a base payload map.
    """
    if not manga_ids:
        return {}

    res = await db.execute(
        select(
            Manga.manga_id,
            Manga.title,
            Manga.average_rating,
            Manga.cover_image_url,
        ).where(Manga.manga_id.in_(list(manga_ids)))
    )
    rows = res.all()

    base_by_id: dict[int, dict] = {}
    for r in rows:
        d = dict(r._mapping)
        mid = int(d["manga_id"])
        base_by_id[mid] = {
            "manga_id": mid,
            "title": d["title"],
            "average_rating": d["average_rating"],
            "cover_image_url": d["cover_image_url"],
            "genres": [],
        }

    return base_by_id


async def attach_genres_to_base(
    db: ClientReadDatabase,
    *,
    manga_ids: Sequence[int],
    base_by_id: dict[int, dict],
) -> None:
    """
    Attach genres onto the base payload map for the given manga_ids.
    """
    if not manga_ids or not base_by_id:
        return

    res = await db.execute(
        select(
            manga_genre.c.manga_id.label("manga_id"),
            Genre.genre_id.label("genre_id"),
            Genre.genre_name.label("genre_name"),
        )
        .select_from(manga_genre.join(Genre, Genre.genre_id == manga_genre.c.genre_id))
        .where(manga_genre.c.manga_id.in_(list(manga_ids)))
        .order_by(manga_genre.c.manga_id, Genre.genre_name)
    )
    genre_rows = res.all()

    for gr in genre_rows:
        g = dict(gr._mapping)
        mid = int(g["manga_id"])
        if mid in base_by_id:
            base_by_id[mid]["genres"].append(
                {"genre_id": int(g["genre_id"]), "genre_name": g["genre_name"]}
            )