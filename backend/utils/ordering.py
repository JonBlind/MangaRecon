"""
Ordering utilities for manga queries and recommendation sorting.

Defines validated order-by fields and a helper to produce SQL ordering
clauses given user input, guarding against invalid columns or directions.
"""

from typing import Dict, Literal
from sqlalchemy import asc, desc
from sqlalchemy.sql import ColumnElement
from backend.db.models.manga import Manga

MangaOrderField = Literal["title", "publication_year", "external_average_rating"]
OrderDirection = Literal["asc", "desc"]

RecommendationOrderField = Literal["score", "title", "external_average_rating"]

MANGA_SORT_OPTIONS: Dict[str, ColumnElement] = {
    "title": Manga.title,
    "publication_year": Manga.publication_year,
    "external_average_rating": Manga.external_average_rating,
}


def get_ordering_clause(field: MangaOrderField, direction: OrderDirection) -> ColumnElement:
    """
    Return the SQL ordering clause for a validated field and direction.
    """

    column = MANGA_SORT_OPTIONS.get(field)
    if column is None:
        raise ValueError(f"Unsupported sort field: {field}")

    if direction == "asc":
        return asc(column).nulls_last()
    if direction == "desc":
        return desc(column).nulls_last()

    raise ValueError(f"Unsupported sort direction: {direction}")
