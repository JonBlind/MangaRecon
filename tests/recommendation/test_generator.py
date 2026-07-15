from collections import Counter
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from backend.config.limits import MAX_RECOMMENDATION_SEEDS
from backend.recommendation.generator import (
    generate_recommendations_for_collection,
    generate_recommendations_for_list,
)
from backend.utils.domain_exceptions import BadRequestError


def make_metadata_profile():
    return {
        "genres": Counter({1: 2, 2: 1}),
        "tags": Counter({10: 1}),
        "demographics": Counter({100: 1}),
        "authors": {500},
        "external_ratings": [8.0],
        "years": [2020],
    }


@pytest.mark.asyncio
async def test_generate_for_collection_raises_when_collection_has_no_manga():
    user_db = AsyncMock()
    manga_db = AsyncMock()
    user_id = uuid.uuid4()

    with patch(
        "backend.recommendation.generator.core.get_manga_ids_in_user_collection",
        new=AsyncMock(return_value=[]),
    ) as get_ids:
        with pytest.raises(BadRequestError) as exc_info:
            await generate_recommendations_for_collection(
                user_id=user_id,
                collection_id=12,
                user_db=user_db,
                manga_db=manga_db,
            )

    error = exc_info.value

    assert error.status_code == 400
    assert error.code == "RECOMMENDATION_SEED_EMPTY"
    assert error.message == (
        "Need at least 1 manga in the collection to generate recommendations."
    )
    assert error.detail == {"collection_id": 12}

    get_ids.assert_awaited_once_with(user_id, 12, user_db)


@pytest.mark.asyncio
async def test_generate_for_collection_composes_core_steps():
    user_db = AsyncMock()
    manga_db = AsyncMock()
    user_id = uuid.uuid4()

    manga_ids = [1, 2, 3]
    metadata_profile = make_metadata_profile()

    candidates = [
        {
            "manga_id": 20,
            "title": "Candidate",
        }
    ]

    scored = [
        {
            "manga_id": 20,
            "title": "Candidate",
            "score": 18.5,
        }
    ]

    with (
        patch(
            "backend.recommendation.generator.core.get_manga_ids_in_user_collection",
            new=AsyncMock(return_value=manga_ids),
        ) as get_ids,
        patch(
            "backend.recommendation.generator.core.get_metadata_profile_for_collection",
            new=AsyncMock(return_value=metadata_profile),
        ) as get_profile,
        patch(
            "backend.recommendation.generator.core.get_candidate_manga",
            new=AsyncMock(return_value=candidates),
        ) as get_candidates,
        patch(
            "backend.recommendation.generator.core.get_scored_recommendations",
            new=AsyncMock(return_value=scored),
        ) as get_scored,
    ):
        result = await generate_recommendations_for_collection(
            user_id=user_id,
            collection_id=7,
            user_db=user_db,
            manga_db=manga_db,
        )

    assert result == {
        "items": scored,
        "seed_total": 3,
        "seed_used": 3,
        "seed_truncated": False,
    }

    get_ids.assert_awaited_once_with(user_id, 7, user_db)

    get_profile.assert_awaited_once_with(
        manga_ids,
        manga_db,
    )

    get_candidates.assert_awaited_once_with(
        excluded_ids=manga_ids,
        genre_ids=[1, 2],
        tag_ids=[10],
        demo_ids=[100],
        db=manga_db,
    )

    get_scored.assert_awaited_once_with(
        candidates,
        metadata_profile,
        manga_db,
    )


@pytest.mark.asyncio
async def test_generate_for_collection_truncates_large_seed_list():
    user_db = AsyncMock()
    manga_db = AsyncMock()

    all_manga_ids = list(range(1, MAX_RECOMMENDATION_SEEDS + 11))
    expected_used_ids = all_manga_ids[:MAX_RECOMMENDATION_SEEDS]

    metadata_profile = {
        "genres": Counter(),
        "tags": Counter(),
        "demographics": Counter(),
        "authors": set(),
        "external_ratings": [],
        "years": [],
    }

    with (
        patch(
            "backend.recommendation.generator.core.get_manga_ids_in_user_collection",
            new=AsyncMock(return_value=all_manga_ids),
        ),
        patch(
            "backend.recommendation.generator.core.get_metadata_profile_for_collection",
            new=AsyncMock(return_value=metadata_profile),
        ) as get_profile,
        patch(
            "backend.recommendation.generator.core.get_candidate_manga",
            new=AsyncMock(return_value=[]),
        ) as get_candidates,
        patch(
            "backend.recommendation.generator.core.get_scored_recommendations",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await generate_recommendations_for_collection(
            user_id=uuid.uuid4(),
            collection_id=4,
            user_db=user_db,
            manga_db=manga_db,
        )

    assert result == {
        "items": [],
        "seed_total": MAX_RECOMMENDATION_SEEDS + 10,
        "seed_used": MAX_RECOMMENDATION_SEEDS,
        "seed_truncated": True,
    }

    get_profile.assert_awaited_once_with(
        expected_used_ids,
        manga_db,
    )

    get_candidates.assert_awaited_once_with(
        excluded_ids=expected_used_ids,
        genre_ids=[],
        tag_ids=[],
        demo_ids=[],
        db=manga_db,
    )


@pytest.mark.asyncio
async def test_generate_for_list_raises_when_list_is_empty():
    db = AsyncMock()

    with pytest.raises(BadRequestError) as exc_info:
        await generate_recommendations_for_list(
            manga_ids=[],
            db=db,
        )

    error = exc_info.value

    assert error.status_code == 400
    assert error.code == "RECOMMENDATION_SEED_EMPTY"
    assert error.message == (
        "Please provide at least one manga to generate recommendations."
    )
    assert error.detail is None


@pytest.mark.asyncio
async def test_generate_for_list_composes_core_steps():
    db = AsyncMock()

    manga_ids = [11, 12]
    metadata_profile = make_metadata_profile()

    candidates = [
        {
            "manga_id": 30,
            "title": "Candidate",
        }
    ]

    scored = [
        {
            "manga_id": 30,
            "title": "Candidate",
            "score": 14.0,
        }
    ]

    with (
        patch(
            "backend.recommendation.generator.core.get_metadata_profile_for_collection",
            new=AsyncMock(return_value=metadata_profile),
        ) as get_profile,
        patch(
            "backend.recommendation.generator.core.get_candidate_manga",
            new=AsyncMock(return_value=candidates),
        ) as get_candidates,
        patch(
            "backend.recommendation.generator.core.get_scored_recommendations",
            new=AsyncMock(return_value=scored),
        ) as get_scored,
    ):
        result = await generate_recommendations_for_list(
            manga_ids=manga_ids,
            db=db,
        )

    assert result == {
        "items": scored,
        "seed_total": 2,
        "seed_used": 2,
        "seed_truncated": False,
    }

    get_profile.assert_awaited_once_with(
        manga_ids,
        db,
    )

    get_candidates.assert_awaited_once_with(
        excluded_ids=manga_ids,
        genre_ids=[1, 2],
        tag_ids=[10],
        demo_ids=[100],
        db=db,
    )

    get_scored.assert_awaited_once_with(
        candidates,
        metadata_profile,
        db,
    )


@pytest.mark.asyncio
async def test_generate_for_list_truncates_large_seed_list():
    db = AsyncMock()

    all_manga_ids = list(range(1, MAX_RECOMMENDATION_SEEDS + 6))
    expected_used_ids = all_manga_ids[:MAX_RECOMMENDATION_SEEDS]

    metadata_profile = {
        "genres": Counter(),
        "tags": Counter(),
        "demographics": Counter(),
        "authors": set(),
        "external_ratings": [],
        "years": [],
    }

    with (
        patch(
            "backend.recommendation.generator.core.get_metadata_profile_for_collection",
            new=AsyncMock(return_value=metadata_profile),
        ) as get_profile,
        patch(
            "backend.recommendation.generator.core.get_candidate_manga",
            new=AsyncMock(return_value=[]),
        ) as get_candidates,
        patch(
            "backend.recommendation.generator.core.get_scored_recommendations",
            new=AsyncMock(return_value=[]),
        ) as get_scored,
    ):
        result = await generate_recommendations_for_list(
            manga_ids=all_manga_ids,
            db=db,
        )

    assert result == {
        "items": [],
        "seed_total": MAX_RECOMMENDATION_SEEDS + 5,
        "seed_used": MAX_RECOMMENDATION_SEEDS,
        "seed_truncated": True,
    }

    get_profile.assert_awaited_once_with(
        expected_used_ids,
        db,
    )

    get_candidates.assert_awaited_once_with(
        excluded_ids=expected_used_ids,
        genre_ids=[],
        tag_ids=[],
        demo_ids=[],
        db=db,
    )

    get_scored.assert_awaited_once_with(
        [],
        metadata_profile,
        db,
    )