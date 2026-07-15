from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services import manga_service
from backend.utils.domain_exceptions import NotFoundError


def make_manga_detail_row(
    *,
    manga_id: int = 1,
    title: str = "Test Manga",
):
    return SimpleNamespace(
        manga_id=manga_id,
        title=title,
        description="A test description.",
        published_date=date(2020, 5, 10),
        external_average_rating=8.4,
        average_rating=7.9,
        author_id=15,
        cover_image_url="https://example.com/cover.jpg",
    )


def make_manga_list_row(
    *,
    manga_id: int,
    title: str,
    average_rating: float | None = None,
    external_average_rating: float | None = None,
    cover_image_url: str | None = None,
):
    return SimpleNamespace(
        manga_id=manga_id,
        title=title,
        description=f"Description for {title}",
        average_rating=average_rating,
        external_average_rating=external_average_rating,
        cover_image_url=cover_image_url,
    )


@pytest.mark.asyncio
async def test_get_manga_detail_returns_manga_with_metadata(
    monkeypatch,
):
    db = MagicMock()
    manga_row = make_manga_detail_row(
        manga_id=42,
        title="Detailed Manga",
    )

    fetch_core = AsyncMock(return_value=manga_row)
    fetch_genres = AsyncMock(
        return_value=[
            SimpleNamespace(
                genre_id=1,
                genre_name="Action",
            ),
            SimpleNamespace(
                genre_id=2,
                genre_name="Adventure",
            ),
        ]
    )
    fetch_tags = AsyncMock(
        return_value=[
            SimpleNamespace(
                tag_id=10,
                tag_name="Time Travel",
            )
        ]
    )
    fetch_demographics = AsyncMock(
        return_value=[
            SimpleNamespace(
                demographic_id=100,
                demographic_name="Shonen",
            )
        ]
    )

    monkeypatch.setattr(
        manga_service,
        "fetch_manga_core_by_id",
        fetch_core,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_genres",
        fetch_genres,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_tags",
        fetch_tags,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_demographics",
        fetch_demographics,
    )

    result = await manga_service.get_manga_detail(
        manga_id=42,
        db=db,
    )

    assert result.manga_id == 42
    assert result.title == "Detailed Manga"
    assert result.description == "A test description."
    assert result.published_date == date(2020, 5, 10)
    assert result.external_average_rating == 8.4
    assert result.average_rating == 7.9
    assert result.author_id == 15
    assert result.cover_image_url == "https://example.com/cover.jpg"

    assert [
        genre.model_dump()
        for genre in result.genres
    ] == [
        {
            "genre_id": 1,
            "genre_name": "Action",
        },
        {
            "genre_id": 2,
            "genre_name": "Adventure",
        },
    ]

    assert [
        tag.model_dump()
        for tag in result.tags
    ] == [
        {
            "tag_id": 10,
            "tag_name": "Time Travel",
        }
    ]

    assert [
        demographic.model_dump()
        for demographic in result.demographics
    ] == [
        {
            "demographic_id": 100,
            "demographic_name": "Shonen",
        }
    ]

    fetch_core.assert_awaited_once_with(
        db,
        manga_id=42,
    )
    fetch_genres.assert_awaited_once_with(
        db,
        manga_id=42,
    )
    fetch_tags.assert_awaited_once_with(
        db,
        manga_id=42,
    )
    fetch_demographics.assert_awaited_once_with(
        db,
        manga_id=42,
    )


@pytest.mark.asyncio
async def test_get_manga_detail_raises_when_manga_missing(
    monkeypatch,
):
    db = MagicMock()

    fetch_core = AsyncMock(return_value=None)
    fetch_genres = AsyncMock()
    fetch_tags = AsyncMock()
    fetch_demographics = AsyncMock()

    monkeypatch.setattr(
        manga_service,
        "fetch_manga_core_by_id",
        fetch_core,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_genres",
        fetch_genres,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_tags",
        fetch_tags,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_manga_demographics",
        fetch_demographics,
    )

    with pytest.raises(NotFoundError) as exc_info:
        await manga_service.get_manga_detail(
            manga_id=999,
            db=db,
        )

    error = exc_info.value

    assert error.status_code == 404
    assert error.code == "MANGA_NOT_FOUND"
    assert error.message == "Manga not found."

    fetch_core.assert_awaited_once_with(
        db,
        manga_id=999,
    )
    fetch_genres.assert_not_awaited()
    fetch_tags.assert_not_awaited()
    fetch_demographics.assert_not_awaited()


@pytest.mark.asyncio
async def test_filter_manga_page_returns_empty_page_without_genre_query(
    monkeypatch,
):
    db = MagicMock()
    statement = MagicMock(name="filter_statement")

    build_filter = MagicMock(return_value=statement)
    count_filtered = AsyncMock(return_value=0)
    fetch_page = AsyncMock(return_value=[])
    fetch_genres = AsyncMock()

    monkeypatch.setattr(
        manga_service,
        "build_filter_stmt",
        build_filter,
    )
    monkeypatch.setattr(
        manga_service,
        "count_filtered_manga",
        count_filtered,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_filtered_manga_page",
        fetch_page,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_genres_for_manga_ids",
        fetch_genres,
    )

    result = await manga_service.filter_manga_page(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
        page=1,
        size=20,
        order_by="title",
        order_dir="asc",
        db=db,
    )

    assert result == {
        "total_results": 0,
        "page": 1,
        "size": 20,
        "items": [],
    }

    build_filter.assert_called_once_with(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    count_filtered.assert_awaited_once_with(
        db,
        stmt=statement,
    )

    fetch_page.assert_awaited_once_with(
        db,
        stmt=statement,
        offset=0,
        limit=20,
        order_by="title",
        order_dir="asc",
    )

    fetch_genres.assert_not_awaited()


@pytest.mark.asyncio
async def test_filter_manga_page_passes_all_filters_and_pagination(
    monkeypatch,
):
    db = MagicMock()
    statement = MagicMock(name="filter_statement")

    rows = [
        make_manga_list_row(
            manga_id=10,
            title="First Manga",
            average_rating=7.5,
            external_average_rating=8.0,
            cover_image_url="first.jpg",
        ),
        make_manga_list_row(
            manga_id=20,
            title="Second Manga",
            average_rating=None,
            external_average_rating=9.1,
            cover_image_url=None,
        ),
    ]

    genre_rows = [
        SimpleNamespace(
            manga_id=10,
            genre_id=1,
            genre_name="Action",
        ),
        SimpleNamespace(
            manga_id=10,
            genre_id=2,
            genre_name="Adventure",
        ),
        SimpleNamespace(
            manga_id=20,
            genre_id=3,
            genre_name="Drama",
        ),
    ]

    build_filter = MagicMock(return_value=statement)
    count_filtered = AsyncMock(return_value=12)
    fetch_page = AsyncMock(return_value=rows)
    fetch_genres = AsyncMock(return_value=genre_rows)

    monkeypatch.setattr(
        manga_service,
        "build_filter_stmt",
        build_filter,
    )
    monkeypatch.setattr(
        manga_service,
        "count_filtered_manga",
        count_filtered,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_filtered_manga_page",
        fetch_page,
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_genres_for_manga_ids",
        fetch_genres,
    )

    result = await manga_service.filter_manga_page(
        genre_ids=[1, 2],
        exclude_genres=[9],
        tag_ids=[10],
        exclude_tags=[99],
        demo_ids=[100],
        exclude_demos=[999],
        title="manga",
        page=2,
        size=5,
        order_by="external_average_rating",
        order_dir="desc",
        db=db,
    )

    assert result["total_results"] == 12
    assert result["page"] == 2
    assert result["size"] == 5
    assert len(result["items"]) == 2

    first = result["items"][0]
    second = result["items"][1]

    assert first.manga_id == 10
    assert first.title == "First Manga"
    assert first.average_rating == 7.5
    assert first.cover_image_url == "first.jpg"
    assert [
        genre.model_dump()
        for genre in first.genres
    ] == [
        {
            "genre_id": 1,
            "genre_name": "Action",
        },
        {
            "genre_id": 2,
            "genre_name": "Adventure",
        },
    ]

    assert second.manga_id == 20
    assert second.title == "Second Manga"
    assert second.average_rating is None
    assert second.cover_image_url is None
    assert [
        genre.model_dump()
        for genre in second.genres
    ] == [
        {
            "genre_id": 3,
            "genre_name": "Drama",
        }
    ]

    build_filter.assert_called_once_with(
        genre_ids=[1, 2],
        exclude_genres=[9],
        tag_ids=[10],
        exclude_tags=[99],
        demo_ids=[100],
        exclude_demos=[999],
        title="manga",
    )

    count_filtered.assert_awaited_once_with(
        db,
        stmt=statement,
    )

    fetch_page.assert_awaited_once_with(
        db,
        stmt=statement,
        offset=5,
        limit=5,
        order_by="external_average_rating",
        order_dir="desc",
    )

    fetch_genres.assert_awaited_once_with(
        db,
        manga_ids=[10, 20],
    )


@pytest.mark.asyncio
async def test_filter_manga_page_leaves_genres_empty_when_no_matches(
    monkeypatch,
):
    db = MagicMock()
    statement = MagicMock(name="filter_statement")

    rows = [
        make_manga_list_row(
            manga_id=50,
            title="No Genre Manga",
            average_rating=6.0,
        )
    ]

    monkeypatch.setattr(
        manga_service,
        "build_filter_stmt",
        MagicMock(return_value=statement),
    )
    monkeypatch.setattr(
        manga_service,
        "count_filtered_manga",
        AsyncMock(return_value=1),
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_filtered_manga_page",
        AsyncMock(return_value=rows),
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_genres_for_manga_ids",
        AsyncMock(return_value=[]),
    )

    result = await manga_service.filter_manga_page(
        genre_ids=[],
        exclude_genres=[],
        tag_ids=[],
        exclude_tags=[],
        demo_ids=[],
        exclude_demos=[],
        title="No Genre",
        page=1,
        size=10,
        order_by="title",
        order_dir="asc",
        db=db,
    )

    assert len(result["items"]) == 1
    assert result["items"][0].manga_id == 50
    assert result["items"][0].genres == []


@pytest.mark.asyncio
async def test_filter_manga_page_groups_duplicate_genre_rows_by_manga(
    monkeypatch,
):
    db = MagicMock()
    statement = MagicMock(name="filter_statement")

    rows = [
        make_manga_list_row(
            manga_id=1,
            title="One",
        ),
        make_manga_list_row(
            manga_id=2,
            title="Two",
        ),
    ]

    genre_rows = [
        SimpleNamespace(
            manga_id="1",
            genre_id="10",
            genre_name="Fantasy",
        ),
        SimpleNamespace(
            manga_id="1",
            genre_id="20",
            genre_name="Comedy",
        ),
        SimpleNamespace(
            manga_id="2",
            genre_id="30",
            genre_name="Mystery",
        ),
    ]

    monkeypatch.setattr(
        manga_service,
        "build_filter_stmt",
        MagicMock(return_value=statement),
    )
    monkeypatch.setattr(
        manga_service,
        "count_filtered_manga",
        AsyncMock(return_value=2),
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_filtered_manga_page",
        AsyncMock(return_value=rows),
    )
    monkeypatch.setattr(
        manga_service,
        "fetch_genres_for_manga_ids",
        AsyncMock(return_value=genre_rows),
    )

    result = await manga_service.filter_manga_page(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
        page=1,
        size=10,
        order_by="title",
        order_dir="asc",
        db=db,
    )

    assert [
        genre.genre_id
        for genre in result["items"][0].genres
    ] == [10, 20]

    assert [
        genre.genre_name
        for genre in result["items"][0].genres
    ] == ["Fantasy", "Comedy"]

    assert [
        genre.genre_id
        for genre in result["items"][1].genres
    ] == [30]