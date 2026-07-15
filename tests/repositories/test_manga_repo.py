from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.repositories import manga_repo


class FakeResult:
    def __init__(
        self,
        *,
        one_or_none_value=None,
        scalar_rows=None,
        rows=None,
        scalar_value=None,
    ):
        self.one_or_none_value = one_or_none_value
        self.scalar_rows = scalar_rows or []
        self.rows = rows or []
        self.scalar_value = scalar_value

    def one_or_none(self):
        return self.one_or_none_value

    def scalars(self):
        return self

    def all(self):
        if self.scalar_rows:
            return self.scalar_rows
        return self.rows

    def scalar_one(self):
        return self.scalar_value


class FakeMappingRow:
    def __init__(self, **values):
        self._mapping = values


@pytest.mark.asyncio
async def test_fetch_manga_core_by_id_returns_row():
    db = MagicMock()
    row = SimpleNamespace(
        manga_id=12,
        title="Test Manga",
    )

    db.execute = AsyncMock(
        return_value=FakeResult(
            one_or_none_value=row,
        )
    )

    result = await manga_repo.fetch_manga_core_by_id(
        db,
        manga_id=12,
    )

    assert result is row
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_manga_core_by_id_returns_none():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            one_or_none_value=None,
        )
    )

    result = await manga_repo.fetch_manga_core_by_id(
        db,
        manga_id=999,
    )

    assert result is None


@pytest.mark.asyncio
async def test_fetch_manga_genres_returns_scalar_rows():
    db = MagicMock()

    genres = [
        SimpleNamespace(
            genre_id=1,
            genre_name="Action",
        ),
        SimpleNamespace(
            genre_id=2,
            genre_name="Fantasy",
        ),
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=genres,
        )
    )

    result = await manga_repo.fetch_manga_genres(
        db,
        manga_id=4,
    )

    assert result == genres
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_manga_tags_returns_scalar_rows():
    db = MagicMock()

    tags = [
        SimpleNamespace(
            tag_id=10,
            tag_name="Time Travel",
        )
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=tags,
        )
    )

    result = await manga_repo.fetch_manga_tags(
        db,
        manga_id=4,
    )

    assert result == tags


@pytest.mark.asyncio
async def test_fetch_manga_demographics_returns_scalar_rows():
    db = MagicMock()

    demographics = [
        SimpleNamespace(
            demographic_id=100,
            demographic_name="Shonen",
        )
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_rows=demographics,
        )
    )

    result = await manga_repo.fetch_manga_demographics(
        db,
        manga_id=4,
    )

    assert result == demographics


def test_build_filter_stmt_without_filters():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "SELECT DISTINCT" in sql
    assert "FROM manga" in sql
    assert "WHERE" not in sql


def test_build_filter_stmt_with_title():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title="naruto",
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    ).lower()

    assert "lower(manga.title) like lower('%naruto%')" in sql


def test_build_filter_stmt_with_included_genres():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=[1, 2],
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "JOIN manga_genre" in sql
    assert "manga_genre.genre_id IN (1, 2)" in sql


def test_build_filter_stmt_with_excluded_genres():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=[3, 4],
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "manga.manga_id NOT IN" in sql
    assert "manga_genre.genre_id IN (3, 4)" in sql


def test_build_filter_stmt_with_included_tags():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=[10, 20],
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "JOIN manga_tag" in sql
    assert "manga_tag.tag_id IN (10, 20)" in sql


def test_build_filter_stmt_with_excluded_tags():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=[30],
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "manga.manga_id NOT IN" in sql
    assert "manga_tag.tag_id IN (30)" in sql


def test_build_filter_stmt_with_included_demographics():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=[100],
        exclude_demos=None,
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "JOIN manga_demographic" in sql
    assert "manga_demographic.demographic_id IN (100)" in sql


def test_build_filter_stmt_with_excluded_demographics():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=[200],
        title=None,
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "manga.manga_id NOT IN" in sql
    assert "manga_demographic.demographic_id IN (200)" in sql


def test_build_filter_stmt_combines_all_filters():
    stmt = manga_repo.build_filter_stmt(
        genre_ids=[1],
        exclude_genres=[2],
        tag_ids=[10],
        exclude_tags=[20],
        demo_ids=[100],
        exclude_demos=[200],
        title="hero",
    )

    sql = str(
        stmt.compile(
            compile_kwargs={
                "literal_binds": True,
            }
        )
    )

    assert "JOIN manga_genre" in sql
    assert "JOIN manga_tag" in sql
    assert "JOIN manga_demographic" in sql
    assert "manga_genre.genre_id IN (1)" in sql
    assert "manga_tag.tag_id IN (10)" in sql
    assert "manga_demographic.demographic_id IN (100)" in sql
    assert "manga_genre.genre_id IN (2)" in sql
    assert "manga_tag.tag_id IN (20)" in sql
    assert "manga_demographic.demographic_id IN (200)" in sql


@pytest.mark.asyncio
async def test_count_filtered_manga_returns_scalar_count():
    db = MagicMock()
    db.execute = AsyncMock(
        return_value=FakeResult(
            scalar_value=17,
        )
    )

    stmt = manga_repo.build_filter_stmt(
        genre_ids=None,
        exclude_genres=None,
        tag_ids=None,
        exclude_tags=None,
        demo_ids=None,
        exclude_demos=None,
        title=None,
    )

    result = await manga_repo.count_filtered_manga(
        db,
        stmt=stmt,
    )

    assert result == 17
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_filtered_manga_page_applies_order_offset_and_limit(
    monkeypatch,
):
    db = MagicMock()

    rows = [
        SimpleNamespace(
            manga_id=1,
            title="A",
        ),
        SimpleNamespace(
            manga_id=2,
            title="B",
        ),
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            rows=rows,
        )
    )

    ordering_clause = MagicMock(name="ordering_clause")
    get_ordering = MagicMock(
        return_value=ordering_clause,
    )

    monkeypatch.setattr(
        manga_repo,
        "get_ordering_clause",
        get_ordering,
    )

    stmt = MagicMock()
    ordered_stmt = MagicMock()
    offset_stmt = MagicMock()
    final_stmt = MagicMock()

    stmt.order_by.return_value = ordered_stmt
    ordered_stmt.offset.return_value = offset_stmt
    offset_stmt.limit.return_value = final_stmt

    result = await manga_repo.fetch_filtered_manga_page(
        db,
        stmt=stmt,
        offset=10,
        limit=5,
        order_by="external_average_rating",
        order_dir="desc",
    )

    assert result == rows

    get_ordering.assert_called_once_with(
        "external_average_rating",
        "desc",
    )
    stmt.order_by.assert_called_once_with(
        ordering_clause,
    )
    ordered_stmt.offset.assert_called_once_with(10)
    offset_stmt.limit.assert_called_once_with(5)
    db.execute.assert_awaited_once_with(final_stmt)


@pytest.mark.asyncio
async def test_fetch_genres_for_manga_ids_returns_empty_without_ids():
    db = MagicMock()
    db.execute = AsyncMock()

    result = await manga_repo.fetch_genres_for_manga_ids(
        db,
        manga_ids=[],
    )

    assert result == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_genres_for_manga_ids_returns_rows():
    db = MagicMock()

    rows = [
        SimpleNamespace(
            manga_id=1,
            genre_id=10,
            genre_name="Fantasy",
        )
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            rows=rows,
        )
    )

    result = await manga_repo.fetch_genres_for_manga_ids(
        db,
        manga_ids=[1, 2],
    )

    assert result == rows
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_manga_list_base_returns_empty_without_ids():
    db = MagicMock()
    db.execute = AsyncMock()

    result = await manga_repo.fetch_manga_list_base(
        db,
        manga_ids=[],
    )

    assert result == {}
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_fetch_manga_list_base_builds_payload_map():
    db = MagicMock()

    rows = [
        FakeMappingRow(
            manga_id="10",
            title="Ten",
            average_rating=7.5,
            cover_image_url="ten.jpg",
        ),
        FakeMappingRow(
            manga_id=20,
            title="Twenty",
            average_rating=None,
            cover_image_url=None,
        ),
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            rows=rows,
        )
    )

    result = await manga_repo.fetch_manga_list_base(
        db,
        manga_ids=[10, 20],
    )

    assert result == {
        10: {
            "manga_id": 10,
            "title": "Ten",
            "average_rating": 7.5,
            "cover_image_url": "ten.jpg",
            "genres": [],
        },
        20: {
            "manga_id": 20,
            "title": "Twenty",
            "average_rating": None,
            "cover_image_url": None,
            "genres": [],
        },
    }


@pytest.mark.asyncio
async def test_attach_genres_to_base_returns_when_ids_empty():
    db = MagicMock()
    db.execute = AsyncMock()

    base_by_id = {
        1: {
            "manga_id": 1,
            "genres": [],
        }
    }

    result = await manga_repo.attach_genres_to_base(
        db,
        manga_ids=[],
        base_by_id=base_by_id,
    )

    assert result is None
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_genres_to_base_returns_when_base_empty():
    db = MagicMock()
    db.execute = AsyncMock()

    result = await manga_repo.attach_genres_to_base(
        db,
        manga_ids=[1],
        base_by_id={},
    )

    assert result is None
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_attach_genres_to_base_adds_matching_genres():
    db = MagicMock()

    genre_rows = [
        FakeMappingRow(
            manga_id="1",
            genre_id="10",
            genre_name="Fantasy",
        ),
        FakeMappingRow(
            manga_id=1,
            genre_id=20,
            genre_name="Adventure",
        ),
        FakeMappingRow(
            manga_id=2,
            genre_id=30,
            genre_name="Drama",
        ),
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            rows=genre_rows,
        )
    )

    base_by_id = {
        1: {
            "manga_id": 1,
            "title": "One",
            "average_rating": 8.0,
            "cover_image_url": None,
            "genres": [],
        },
        2: {
            "manga_id": 2,
            "title": "Two",
            "average_rating": 7.0,
            "cover_image_url": None,
            "genres": [],
        },
    }

    result = await manga_repo.attach_genres_to_base(
        db,
        manga_ids=[1, 2],
        base_by_id=base_by_id,
    )

    assert result is None

    assert base_by_id[1]["genres"] == [
        {
            "genre_id": 10,
            "genre_name": "Fantasy",
        },
        {
            "genre_id": 20,
            "genre_name": "Adventure",
        },
    ]

    assert base_by_id[2]["genres"] == [
        {
            "genre_id": 30,
            "genre_name": "Drama",
        }
    ]


@pytest.mark.asyncio
async def test_attach_genres_to_base_skips_unknown_manga_id():
    db = MagicMock()

    genre_rows = [
        FakeMappingRow(
            manga_id=999,
            genre_id=10,
            genre_name="Fantasy",
        )
    ]

    db.execute = AsyncMock(
        return_value=FakeResult(
            rows=genre_rows,
        )
    )

    base_by_id = {
        1: {
            "manga_id": 1,
            "genres": [],
        }
    }

    await manga_repo.attach_genres_to_base(
        db,
        manga_ids=[1],
        base_by_id=base_by_id,
    )

    assert base_by_id[1]["genres"] == []