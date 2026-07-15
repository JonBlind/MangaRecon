from collections import Counter
from datetime import date
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.recommendation.core import (
    get_candidate_manga,
    get_manga_ids_in_user_collection,
    get_metadata_profile_for_collection,
    get_scored_recommendations,
)


class FakeResult:
    """
    Minimal stand-in for the SQLAlchemy Result objects used by core.py.

    Different core functions call:
    - scalar_one_or_none()
    - fetchall()
    - mappings().all()
    """

    def __init__(
        self,
        *,
        scalar_value=None,
        rows=None,
        mapping_rows=None,
    ):
        self.scalar_value = scalar_value
        self.rows = rows or []
        self.mapping_rows = mapping_rows or []

    def scalar_one_or_none(self):
        return self.scalar_value

    def fetchall(self):
        return self.rows

    def mappings(self):
        return self

    def all(self):
        return self.mapping_rows


@pytest.mark.asyncio
async def test_get_manga_ids_returns_empty_when_collection_not_owned():
    db = AsyncMock()
    db.execute.return_value = FakeResult(scalar_value=None)

    user_id = uuid.uuid4()

    result = await get_manga_ids_in_user_collection(
        user_id=user_id,
        collection_id=12,
        db=db,
    )

    assert result == []
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_manga_ids_returns_deduplicated_ids():
    db = AsyncMock()
    db.execute.side_effect = [
        FakeResult(scalar_value=object()),
        FakeResult(rows=[(10,), (20,), (10,), (30,)]),
    ]

    result = await get_manga_ids_in_user_collection(
        user_id=uuid.uuid4(),
        collection_id=4,
        db=db,
    )

    assert set(result) == {10, 20, 30}
    assert len(result) == 3
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_manga_ids_returns_empty_on_database_error():
    db = AsyncMock()
    db.execute.side_effect = SQLAlchemyError("database unavailable")

    result = await get_manga_ids_in_user_collection(
        user_id=uuid.uuid4(),
        collection_id=4,
        db=db,
    )

    assert result == []


@pytest.mark.asyncio
async def test_metadata_profile_collects_all_metadata():
    db = AsyncMock()
    db.execute.side_effect = [
        # Genres
        FakeResult(rows=[(1,), (1,), (2,)]),
        # Tags
        FakeResult(rows=[(10,), (20,), (10,)]),
        # Demographics
        FakeResult(rows=[(100,), (100,), (200,)]),
        # Authors
        FakeResult(rows=[(500,), (600,), (500,)]),
        # External ratings
        FakeResult(rows=[(8.5,), (None,), (7.5,)]),
        # Publication dates
        FakeResult(
            rows=[
                (date(2001, 1, 1),),
                (None,),
                (date(2005, 6, 15),),
            ]
        ),
    ]

    profile = await get_metadata_profile_for_collection(
        manga_ids=[1, 2, 3],
        db=db,
    )

    assert profile["genres"] == Counter({1: 2, 2: 1})
    assert profile["tags"] == Counter({10: 2, 20: 1})
    assert profile["demographics"] == Counter({100: 2, 200: 1})
    assert profile["authors"] == {500, 600}
    assert profile["external_ratings"] == [8.5, 7.5]
    assert profile["years"] == [2001, 2005]
    assert db.execute.await_count == 6


@pytest.mark.asyncio
async def test_metadata_profile_returns_empty_profile_on_database_error():
    db = AsyncMock()
    db.execute.side_effect = SQLAlchemyError("database unavailable")

    profile = await get_metadata_profile_for_collection(
        manga_ids=[1, 2],
        db=db,
    )

    assert profile == {
        "genres": Counter(),
        "tags": Counter(),
        "demographics": Counter(),
        "authors": set(),
        "external_ratings": [],
        "years": [],
    }


@pytest.mark.asyncio
async def test_get_candidate_manga_returns_mapping_rows():
    db = AsyncMock()

    candidate_rows = [
        {
            "manga_id": 10,
            "title": "Candidate One",
            "author_id": 100,
            "description": "Description one",
            "published_date": date(2020, 1, 1),
            "external_average_rating": 8.4,
            "average_rating": 7.9,
            "cover_image_url": "one.jpg",
        },
        {
            "manga_id": 20,
            "title": "Candidate Two",
            "author_id": 200,
            "description": "Description two",
            "published_date": date(2018, 1, 1),
            "external_average_rating": 7.8,
            "average_rating": 7.0,
            "cover_image_url": "two.jpg",
        },
    ]

    db.execute.return_value = FakeResult(mapping_rows=candidate_rows)

    result = await get_candidate_manga(
        excluded_ids=[1, 2],
        genre_ids=[3],
        tag_ids=[4],
        demo_ids=[5],
        db=db,
        max_candidates=50,
    )

    assert result == candidate_rows
    assert result[0]["manga_id"] == 10
    assert result[1]["title"] == "Candidate Two"
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_candidate_manga_returns_empty_on_error():
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("unexpected query failure")

    result = await get_candidate_manga(
        excluded_ids=[1],
        genre_ids=[2],
        tag_ids=[3],
        demo_ids=[4],
        db=db,
    )

    assert result == []


@pytest.mark.asyncio
async def test_scored_recommendations_returns_empty_for_no_candidates():
    db = AsyncMock()

    result = await get_scored_recommendations(
        candidates=[],
        metadata_profile={
            "genres": Counter(),
            "tags": Counter(),
            "demographics": Counter(),
            "authors": set(),
            "external_ratings": [],
            "years": [],
        },
        db=db,
    )

    assert result == []
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_scored_recommendations_calculates_breakdown_and_sorts():
    db = AsyncMock()

    # The scorer executes four metadata queries in this order:
    # genres, tags, demographics, authors.
    db.execute.side_effect = [
        FakeResult(
            rows=[
                (101, 1),
                (102, 2),
            ]
        ),
        FakeResult(
            rows=[
                (101, 10),
            ]
        ),
        FakeResult(
            rows=[
                (101, 100),
            ]
        ),
        FakeResult(
            rows=[
                (101, 500),
            ]
        ),
    ]

    candidates = [
        {
            "manga_id": 101,
            "title": "Strong Match",
            "external_average_rating": 8.0,
            "published_date": date(2004, 1, 1),
            "cover_image_url": "strong.jpg",
        },
        {
            "manga_id": 102,
            "title": "Weak Match",
            "external_average_rating": 5.0,
            "published_date": date(1990, 1, 1),
            "cover_image_url": "weak.jpg",
        },
    ]

    metadata_profile = {
        "genres": Counter({1: 2, 2: 1}),
        "tags": Counter({10: 2}),
        "demographics": Counter({100: 1}),
        "authors": {500},
        "external_ratings": [8.0, 6.0],
        "years": [2000, 2004],
    }

    result = await get_scored_recommendations(
        candidates=candidates,
        metadata_profile=metadata_profile,
        db=db,
    )

    assert [item["manga_id"] for item in result] == [101, 102]

    strong = result[0]

    assert strong["title"] == "Strong Match"
    assert strong["external_average_rating"] == 8.0
    assert strong["cover_image_url"] == "strong.jpg"

    assert strong["details"] == {
        # Genre 1 occurs twice in the seed profile:
        # 2 occurrences × weight 2 = 4
        "genre_score": 4,
        # Tag 10 occurs twice:
        # 2 occurrences × weight 3 = 6
        "tag_score": 6,
        # Demographic 100 occurs once:
        # 1 occurrence × weight 1.25 = 1.25
        "demo_score": 1.25,
        # Candidate shares author 500.
        "author_score": 3,
        # Seed average is 7.0; candidate is 8.0:
        # 5 - abs(8 - 7) = 4
        "rating_score": 4.0,
        # Seed average year is 2002; candidate is 2004:
        # 5 - (2 × 0.5) = 4
        "year_score": 4.0,
    }

    assert strong["score"] == 22.25

    weak = result[1]

    assert weak["details"]["genre_score"] == 2
    assert weak["details"]["tag_score"] == 0
    assert weak["details"]["demo_score"] == 0
    assert weak["details"]["author_score"] == 0
    assert weak["details"]["rating_score"] == 3.0
    assert weak["details"]["year_score"] == 0
    assert weak["score"] == 5.0

    assert db.execute.await_count == 4


@pytest.mark.asyncio
async def test_scoring_handles_missing_seed_averages_and_candidate_values():
    db = AsyncMock()
    db.execute.side_effect = [
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
        FakeResult(rows=[]),
    ]

    candidates = [
        {
            "manga_id": 101,
            "title": "Sparse Metadata",
            "external_average_rating": None,
            "published_date": None,
            "cover_image_url": None,
        }
    ]

    metadata_profile = {
        "genres": Counter(),
        "tags": Counter(),
        "demographics": Counter(),
        "authors": set(),
        "external_ratings": [],
        "years": [],
    }

    result = await get_scored_recommendations(
        candidates=candidates,
        metadata_profile=metadata_profile,
        db=db,
    )

    assert result == [
        {
            "manga_id": 101,
            "title": "Sparse Metadata",
            "external_average_rating": None,
            "cover_image_url": None,
            "score": 0.0,
            "details": {
                "genre_score": 0,
                "tag_score": 0,
                "demo_score": 0.0,
                "author_score": 0,
                "rating_score": 0,
                "year_score": 0,
            },
        }
    ]