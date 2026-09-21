"""Read-only inventory of titles affected by the explicit-content policy."""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import func, or_, select
from sqlalchemy.engine import make_url

from backend.content_safety.policy import (
    EXPLICIT_GENRE_NAMES,
    NORMALIZED_ADULT_GENRE_NAMES,
)
from backend.db.client_db import ClientReadDatabase
from backend.db.models.genre import Genre
from backend.db.models.join_tables import manga_genre, manga_tag
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection
from backend.db.models.rating import Rating
from backend.db.models.tag import Tag
from backend.dependencies import (
    dispose_database_engines,
    get_manga_read_db,
    get_user_read_db,
    settings as database_settings,
)


@dataclass(frozen=True, slots=True)
class CatalogContentImpact:
    manga_id: int
    title: str
    category: str
    matched_genres: tuple[str, ...]
    ratings: int
    collection_links: int
    cover_url: str | None
    classified_adult: bool


@dataclass(frozen=True, slots=True)
class CatalogTagImpact:
    tag_id: int
    tag_name: str
    safe_titles: int
    adult_titles: int


def _category(matched_genres: tuple[str, ...]) -> str:
    normalized = {genre.casefold() for genre in matched_genres}

    if normalized.intersection(
        genre.casefold() for genre in EXPLICIT_GENRE_NAMES
    ):
        return "explicit"

    if "adult" in normalized:
        return "adult_opt_in"

    return "classification_mismatch"


async def inventory_catalog_content(
    catalog_db: ClientReadDatabase,
    user_db: ClientReadDatabase,
) -> tuple[CatalogContentImpact, ...]:
    """Inspect existing records and user links without changing anything."""
    normalized_genre = func.lower(func.btrim(Genre.genre_name))
    flagged_ids = (
        select(manga_genre.c.manga_id)
        .join(Genre, manga_genre.c.genre_id == Genre.genre_id)
        .where(normalized_genre.in_(NORMALIZED_ADULT_GENRE_NAMES))
    )
    stmt = (
        select(
            Manga.manga_id,
            Manga.title,
            Manga.cover_image_url,
            Manga.is_adult_content,
            Genre.genre_name,
        )
        .select_from(Manga)
        .outerjoin(manga_genre, manga_genre.c.manga_id == Manga.manga_id)
        .outerjoin(Genre, Genre.genre_id == manga_genre.c.genre_id)
        .where(
            or_(
                Manga.is_adult_content.is_(True),
                Manga.manga_id.in_(flagged_ids),
            )
        )
        .order_by(Manga.manga_id)
    )
    rows = (await catalog_db.execute(stmt)).all()
    grouped: dict[int, dict] = {}

    for row in rows:
        manga_id = int(row.manga_id)
        if manga_id not in grouped:
            grouped[manga_id] = {
                "title": row.title,
                "cover_url": row.cover_image_url,
                "classified_adult": bool(row.is_adult_content),
                "genres": set(),
            }

        if (
            row.genre_name
            and row.genre_name.strip().casefold()
            in NORMALIZED_ADULT_GENRE_NAMES
        ):
            grouped[manga_id]["genres"].add(row.genre_name.strip())

    # The catalog role cannot read user tables; count links with UserReader.
    ratings: dict[int, int] = {}
    collection_links: dict[int, int] = {}
    manga_ids = tuple(grouped)
    for start in range(0, len(manga_ids), 500):
        batch = manga_ids[start:start + 500]
        rating_rows = await user_db.execute(
            select(Rating.manga_id, func.count())
            .where(Rating.manga_id.in_(batch))
            .group_by(Rating.manga_id)
        )
        ratings.update((int(manga_id), int(count)) for manga_id, count in rating_rows.all())
        collection_rows = await user_db.execute(
            select(MangaCollection.manga_id, func.count())
            .where(MangaCollection.manga_id.in_(batch))
            .group_by(MangaCollection.manga_id)
        )
        collection_links.update(
            (int(manga_id), int(count)) for manga_id, count in collection_rows.all()
        )

    return tuple(
        CatalogContentImpact(
            manga_id=manga_id,
            title=data["title"],
            category=_category(tuple(data["genres"])),
            matched_genres=tuple(sorted(data["genres"])),
            ratings=ratings.get(manga_id, 0),
            collection_links=collection_links.get(manga_id, 0),
            cover_url=data["cover_url"],
            classified_adult=data["classified_adult"],
        )
        for manga_id, data in grouped.items()
    )


async def inventory_tag_visibility(
    db: ClientReadDatabase,
) -> tuple[CatalogTagImpact, ...]:
    """List all tag labels and whether they remain attached to safe titles."""
    stmt = (
        select(
            Tag.tag_id,
            Tag.tag_name,
            func.count(Manga.manga_id)
            .filter(Manga.is_adult_content.is_(False))
            .label("safe_titles"),
            func.count(Manga.manga_id)
            .filter(Manga.is_adult_content.is_(True))
            .label("adult_titles"),
        )
        .select_from(Tag)
        .outerjoin(manga_tag, manga_tag.c.tag_id == Tag.tag_id)
        .outerjoin(Manga, Manga.manga_id == manga_tag.c.manga_id)
        .group_by(Tag.tag_id, Tag.tag_name)
        .order_by(Tag.tag_name)
    )
    return tuple(
        CatalogTagImpact(
            tag_id=int(row.tag_id),
            tag_name=row.tag_name,
            safe_titles=int(row.safe_titles),
            adult_titles=int(row.adult_titles),
        )
        for row in (await db.execute(stmt)).all()
    )


def _csv_text(value: str) -> str:
    """Keep untrusted provider titles from becoming spreadsheet formulas."""
    return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value


def _hosted_cover(url: str | None) -> bool:
    if not url:
        return False

    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "mangarecon.com"
        and parsed.path.startswith("/covers/")
    )


def write_inventory_csv(
    path: Path,
    items: tuple[CatalogContentImpact, ...],
) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "manga_id", "title", "category", "matched_genres",
                "ratings", "collection_links", "hosted_cover", "cover_url",
                "classified_adult",
            )
        )
        for item in items:
            writer.writerow(
                (
                    item.manga_id,
                    _csv_text(item.title),
                    item.category,
                    ", ".join(sorted(item.matched_genres)),
                    item.ratings,
                    item.collection_links,
                    _hosted_cover(item.cover_url),
                    item.cover_url or "",
                    item.classified_adult,
                )
            )


def write_tag_csv(path: Path, items: tuple[CatalogTagImpact, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.writer(output)
        writer.writerow(("tag_id", "tag_name", "safe_titles", "adult_titles"))
        for item in items:
            writer.writerow(
                (
                    item.tag_id, _csv_text(item.tag_name),
                    item.safe_titles, item.adult_titles,
                )
            )


def print_summary(items: tuple[CatalogContentImpact, ...]) -> None:
    for category in ("explicit", "adult_opt_in", "classification_mismatch"):
        matches = [item for item in items if item.category == category]
        print(
            f"{category}: titles={len(matches)}; "
            f"ratings={sum(item.ratings for item in matches)}; "
            f"collection_links={sum(item.collection_links for item in matches)}; "
            f"hosted_covers={sum(_hosted_cover(item.cover_url) for item in matches)}."
        )

    print("Read-only inventory: no records or covers were changed.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional CSV with each affected title and user-link counts.",
    )
    parser.add_argument(
        "--tags-output",
        type=Path,
        help="Optional CSV of every tag and its safe/adult title counts.",
    )
    arguments = parser.parse_args(argv)

    if not database_settings.manga_read or not database_settings.user_read:
        print("MangaReaderDB and UserReaderDB must both be configured.", file=sys.stderr)
        return 1

    catalog_target = make_url(database_settings.manga_read)
    user_target = make_url(database_settings.user_read)
    if (
        (catalog_target.host or "").casefold() != (user_target.host or "").casefold()
        or catalog_target.database != user_target.database
        or (catalog_target.port or 5432) != (user_target.port or 5432)
    ):
        print(
            "MangaReaderDB and UserReaderDB must target the same host, port, "
            "and database.",
            file=sys.stderr,
        )
        return 1

    print(
        "Read-only database target: "
        f"host={catalog_target.host} database={catalog_target.database} "
        f"catalog_user={catalog_target.username} user_data_user={user_target.username}"
    )

    async def run() -> tuple[tuple[CatalogContentImpact, ...], tuple[CatalogTagImpact, ...]]:
        try:
            async with aclosing(get_manga_read_db()) as provider:
                catalog_db = await anext(provider)
                async with aclosing(get_user_read_db()) as user_provider:
                    user_db = await anext(user_provider)
                    items = await inventory_catalog_content(catalog_db, user_db)
                    tags = (
                        await inventory_tag_visibility(catalog_db)
                        if arguments.tags_output else ()
                    )
                    return items, tags
        finally:
            await dispose_database_engines()

    try:
        items, tags = asyncio.run(run())
        print_summary(items)
        if arguments.output:
            write_inventory_csv(arguments.output, items)
            print(f"Wrote {len(items)} inventory rows to {arguments.output}.")
        if arguments.tags_output:
            write_tag_csv(arguments.tags_output, tags)
            print(f"Wrote {len(tags)} tag rows to {arguments.tags_output}.")
    except Exception as exc:
        print(f"Catalog content inventory failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
