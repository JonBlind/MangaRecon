from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.schemas.manga import (
    DemographicRead,
    GenreRead,
    MangaListItem,
    MangaRead,
    TagRead,
)


def test_genre_read_accepts_valid_data():
    genre = GenreRead(
        genre_id=1,
        genre_name="Action",
    )

    assert genre.genre_id == 1
    assert genre.genre_name == "Action"


def test_genre_read_supports_from_attributes():
    orm_genre = SimpleNamespace(
        genre_id=1,
        genre_name="Action",
    )

    genre = GenreRead.model_validate(
        orm_genre
    )

    assert genre.genre_id == 1
    assert genre.genre_name == "Action"


def test_tag_read_supports_from_attributes():
    orm_tag = SimpleNamespace(
        tag_id=2,
        tag_name="Time Travel",
    )

    tag = TagRead.model_validate(
        orm_tag
    )

    assert tag.tag_id == 2
    assert tag.tag_name == "Time Travel"


def test_demographic_read_supports_from_attributes():
    orm_demographic = SimpleNamespace(
        demographic_id=3,
        demographic_name="Seinen",
    )

    demographic = DemographicRead.model_validate(
        orm_demographic
    )

    assert demographic.demographic_id == 3
    assert demographic.demographic_name == "Seinen"


def test_metadata_read_schemas_require_all_fields():
    with pytest.raises(ValidationError):
        GenreRead(
            genre_id=1,
        )

    with pytest.raises(ValidationError):
        TagRead(
            tag_name="Time Travel",
        )

    with pytest.raises(ValidationError):
        DemographicRead(
            demographic_id=3,
        )


def test_manga_read_accepts_complete_payload():
    manga = MangaRead(
        manga_id=10,
        title="Berserk",
        description="A dark fantasy manga",
        published_date=date(1989, 8, 25),
        external_average_rating=9.4,
        average_rating=9.0,
        author_id=1,
        genres=[
            {
                "genre_id": 1,
                "genre_name": "Action",
            }
        ],
        tags=[
            {
                "tag_id": 2,
                "tag_name": "Dark Fantasy",
            }
        ],
        demographics=[
            {
                "demographic_id": 3,
                "demographic_name": "Seinen",
            }
        ],
        cover_image_url="https://example.com/cover.jpg",
    )

    assert manga.manga_id == 10
    assert manga.title == "Berserk"
    assert manga.published_date == date(1989, 8, 25)
    assert manga.external_average_rating == 9.4
    assert manga.average_rating == 9.0
    assert manga.author_id == 1
    assert manga.cover_image_url == (
        "https://example.com/cover.jpg"
    )

    assert manga.genres == [
        GenreRead(
            genre_id=1,
            genre_name="Action",
        )
    ]

    assert manga.tags == [
        TagRead(
            tag_id=2,
            tag_name="Dark Fantasy",
        )
    ]

    assert manga.demographics == [
        DemographicRead(
            demographic_id=3,
            demographic_name="Seinen",
        )
    ]


def test_manga_read_accepts_optional_null_fields():
    manga = MangaRead(
        manga_id=10,
        title="Berserk",
        description=None,
        published_date=None,
        external_average_rating=None,
        average_rating=None,
        author_id=None,
        cover_image_url=None,
    )

    assert manga.description is None
    assert manga.published_date is None
    assert manga.external_average_rating is None
    assert manga.average_rating is None
    assert manga.author_id is None
    assert manga.cover_image_url is None

    assert manga.genres == []
    assert manga.tags == []
    assert manga.demographics == []


def test_manga_read_requires_author_id_even_though_it_may_be_none():
    with pytest.raises(ValidationError) as exc_info:
        MangaRead(
            manga_id=10,
            title="Berserk",
        )

    assert any(
        error["loc"] == ("author_id",)
        for error in exc_info.value.errors()
    )


def test_manga_read_supports_from_attributes():
    orm_manga = SimpleNamespace(
        manga_id=10,
        title="Monster",
        description=None,
        published_date=date(1994, 12, 5),
        external_average_rating=9.0,
        average_rating=8.8,
        author_id=5,
        genres=[
            SimpleNamespace(
                genre_id=1,
                genre_name="Mystery",
            )
        ],
        tags=[
            SimpleNamespace(
                tag_id=2,
                tag_name="Psychological",
            )
        ],
        demographics=[
            SimpleNamespace(
                demographic_id=3,
                demographic_name="Seinen",
            )
        ],
        cover_image_url=None,
    )

    manga = MangaRead.model_validate(
        orm_manga
    )

    assert manga.manga_id == 10
    assert manga.title == "Monster"
    assert manga.genres[0].genre_name == "Mystery"
    assert manga.tags[0].tag_name == "Psychological"
    assert (
        manga.demographics[0].demographic_name
        == "Seinen"
    )


def test_manga_read_default_lists_are_not_shared():
    first = MangaRead(
        manga_id=1,
        title="One",
        author_id=None,
    )
    second = MangaRead(
        manga_id=2,
        title="Two",
        author_id=None,
    )

    first.genres.append(
        GenreRead(
            genre_id=1,
            genre_name="Action",
        )
    )
    first.tags.append(
        TagRead(
            tag_id=1,
            tag_name="Adventure",
        )
    )
    first.demographics.append(
        DemographicRead(
            demographic_id=1,
            demographic_name="Shonen",
        )
    )

    assert second.genres == []
    assert second.tags == []
    assert second.demographics == []


def test_manga_list_item_accepts_minimum_payload():
    item = MangaListItem(
        manga_id=10,
        title="Berserk",
    )

    assert item.manga_id == 10
    assert item.title == "Berserk"
    assert item.genres == []
    assert item.average_rating is None
    assert item.cover_image_url is None


def test_manga_list_item_parses_nested_genres():
    item = MangaListItem(
        manga_id=10,
        title="Berserk",
        genres=[
            {
                "genre_id": 1,
                "genre_name": "Action",
            }
        ],
        average_rating=9.4,
        cover_image_url="https://example.com/cover.jpg",
    )

    assert item.genres == [
        GenreRead(
            genre_id=1,
            genre_name="Action",
        )
    ]
    assert item.average_rating == 9.4


def test_manga_list_item_supports_from_attributes():
    orm_item = SimpleNamespace(
        manga_id=10,
        title="Berserk",
        genres=[
            SimpleNamespace(
                genre_id=1,
                genre_name="Action",
            )
        ],
        average_rating=9.4,
        cover_image_url=None,
    )

    item = MangaListItem.model_validate(
        orm_item
    )

    assert item.manga_id == 10
    assert item.genres[0].genre_name == "Action"


def test_manga_list_item_default_genre_lists_are_not_shared():
    first = MangaListItem(
        manga_id=1,
        title="One",
    )
    second = MangaListItem(
        manga_id=2,
        title="Two",
    )

    first.genres.append(
        GenreRead(
            genre_id=1,
            genre_name="Action",
        )
    )

    assert second.genres == []