from types import SimpleNamespace

import pytest

from sqlalchemy import select

from backend.content_safety.policy import (
    CatalogContentExcluded,
    check_catalog_ingestion_genres,
    genres_are_adult_content,
)
from backend.content_safety.visibility import (
    restrict_manga_visibility,
    viewer_allows_adult_content,
)
from backend.db.models.manga import Manga


def test_restricted_genres_are_classified_case_insensitively() -> None:
    for genre_name in (
        "Adult",
        "hentai",
        " LOLICON ",
        "Shotacon",
        "SMUT",
    ):
        assert genres_are_adult_content([genre_name]) is True


def test_mature_and_identity_genres_are_not_blanket_restricted() -> None:
    assert genres_are_adult_content(
        ["Mature", "Yaoi", "Yuri", "Seinen"]
    ) is False


@pytest.mark.parametrize("name", [" HENTAI ", "smut", "Lolicon", "SHOTACON"])
def test_explicit_genres_are_excluded_from_ingestion(name: str) -> None:
    with pytest.raises(CatalogContentExcluded):
        check_catalog_ingestion_genres(("Action", name))

def test_adult_only_and_mature_titles_are_allowed() -> None:
    check_catalog_ingestion_genres(("Adult", "Adventure"))
    check_catalog_ingestion_genres(("Mature", "Seinen", "Action"))


def test_viewer_must_be_authenticated_and_explicitly_opted_in() -> None:
    assert viewer_allows_adult_content(None) is False
    assert viewer_allows_adult_content(SimpleNamespace()) is False
    assert viewer_allows_adult_content(
        SimpleNamespace(show_adult_content=False)
    ) is False
    assert viewer_allows_adult_content(
        SimpleNamespace(show_adult_content=True)
    ) is True


def test_safe_visibility_adds_fail_closed_catalog_predicate() -> None:
    statement = restrict_manga_visibility(
        select(Manga.manga_id),
        include_adult=False,
    )

    assert "manga.is_adult_content IS false" in str(statement)


def test_opted_in_visibility_does_not_add_catalog_predicate() -> None:
    statement = restrict_manga_visibility(
        select(Manga.manga_id),
        include_adult=True,
    )

    assert "is_adult_content" not in str(statement)
