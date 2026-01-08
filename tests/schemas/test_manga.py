from datetime import date
import pytest
from pydantic import ValidationError

from backend.schemas.manga import (
    GenreRead,
    TagRead,
    DemographicRead,
    MangaRead,
    MangaListItem,
)


def test_genre_read_instantiates():
    obj = GenreRead(genre_id=1, genre_name="Action")
    assert obj.genre_id == 1
    assert obj.genre_name == "Action"


def test_manga_list_item_instantiates():
    obj = MangaListItem(manga_id=1, title="Bleach", average_rating=8.5)
    assert obj.manga_id == 1
    assert obj.title == "Bleach"
    assert obj.average_rating == 8.5


def test_manga_read_minimal_instantiates_with_defaults():
    obj = MangaRead(
        manga_id=1,
        title="Bleach",
        author_id=10,
    )
    assert obj.manga_id == 1
    assert obj.title == "Bleach"
    assert obj.author_id == 10
    assert obj.description is None
    assert obj.published_date is None
    assert obj.genres == []
    assert obj.tags == []
    assert obj.demographics == []


def test_manga_read_all_fields_instantiates():
    obj = MangaRead(
        manga_id=1,
        title="Bleach",
        description="Soul reapers",
        published_date=date(2001, 8, 7),
        external_average_rating=7.9,
        average_rating=8.5,
        author_id=10,
        genres=[GenreRead(genre_id=1, genre_name="Action")],
        tags=[TagRead(tag_id=2, tag_name="Shinigami")],
        demographics=[DemographicRead(demographic_id=3, demographic_name="Shonen")],
    )
    assert obj.description == "Soul reapers"
    assert obj.genres[0].genre_name == "Action"
    assert obj.tags[0].tag_name == "Shinigami"
    assert obj.demographics[0].demographic_name == "Shonen"


def test_manga_read_required_fields_enforced():
    with pytest.raises(ValidationError):
        MangaRead(title="Missing IDs")

def test_manga_read_lists_do_not_leak_between_instances():
    a = MangaRead(manga_id=1, title="A", author_id=1)
    b = MangaRead(manga_id=2, title="B", author_id=1)

    a.genres.append(GenreRead(genre_id=1, genre_name="Action"))
    assert b.genres == []
