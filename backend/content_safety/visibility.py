from __future__ import annotations

from typing import Protocol

from sqlalchemy.sql import Select

from backend.db.models.manga import Manga


class _AdultContentPreference(Protocol):
    show_adult_content: bool


def viewer_allows_adult_content(
    user: _AdultContentPreference | None,
) -> bool:
    """Allow adult content only for an authenticated user who opted in."""
    return bool(
        user is not None
        and getattr(user, "show_adult_content", False) is True
    )


def restrict_manga_visibility(
    statement: Select,
    *,
    include_adult: bool,
) -> Select:
    """Apply MangaRecon's default-safe catalog rule to a select statement."""
    if include_adult:
        return statement

    return statement.where(
        Manga.is_adult_content.is_(False)
    )
