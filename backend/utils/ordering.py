from typing import Literal, TypeVar, Dict
from sqlalchemy.sql import ColumnElement
from sqlalchemy import asc, desc
from backend.db.models.manga import Manga

MangaOrderField = Literal["title", "published_date", "external_average_rating"]
MangaOrderDirection = Literal["asc", "desc"]

MANGA_SORT_OPTIONS: Dict[str, ColumnElement] = {
    "title": Manga.title,
    "published_date": Manga.published_date,
    "external_average_rating": Manga.external_average_rating,
}

def get_ordering_clause(
    field: MangaOrderField,
    direction: MangaOrderDirection
) -> ColumnElement:
    """
    Returns the correct ordering clause based on field and direction.

    Args:
        field: The field name as a validated string literal.
        direction: Either 'asc' or 'desc'.

    Returns:
        A SQLAlchemy ordering clause.
    """
    column = MANGA_SORT_OPTIONS[field]
    return asc(column) if direction == "asc" else desc(column)
