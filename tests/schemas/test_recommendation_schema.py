import pytest
from pydantic import ValidationError

from backend.config.limits import MAX_QUERY_LIST_SEEDS
from backend.schemas.recommendation import (
    RecommendationQueryListRequest,
)


def test_query_list_accepts_maximum_number_of_seeds():
    manga_ids = list(range(1, MAX_QUERY_LIST_SEEDS + 1))

    payload = RecommendationQueryListRequest(
        manga_ids=manga_ids,
    )

    assert payload.manga_ids == manga_ids


def test_query_list_rejects_more_than_maximum_seeds():
    manga_ids = list(range(1, MAX_QUERY_LIST_SEEDS + 2))

    with pytest.raises(ValidationError):
        RecommendationQueryListRequest(
            manga_ids=manga_ids,
        )
