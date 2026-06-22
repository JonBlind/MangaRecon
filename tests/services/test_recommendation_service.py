import pytest

from backend.services.recommendation_service import _sort_items
from backend.utils.domain_exceptions import BadRequestError
from backend.services.recommendation_service import get_recommendations_for_query_list_page


def test_sort_items_by_score_desc():
    items = [
        {"title": "B", "score": 2.0},
        {"title": "A", "score": 5.0},
        {"title": "C", "score": 3.0},
    ]

    _sort_items(items, order_by="score", order_dir="desc")

    assert [item["title"] for item in items] == ["A", "C", "B"]


def test_sort_items_by_score_asc():
    items = [
        {"title": "B", "score": 2.0},
        {"title": "A", "score": 5.0},
        {"title": "C", "score": 3.0},
    ]

    _sort_items(items, order_by="score", order_dir="asc")

    assert [item["title"] for item in items] == ["B", "C", "A"]


def test_sort_items_by_title_asc_case_insensitive():
    items = [
        {"title": "zebra", "score": 5.0},
        {"title": "Apple", "score": 1.0},
        {"title": "banana", "score": 3.0},
    ]

    _sort_items(items, order_by="title", order_dir="asc")

    assert [item["title"] for item in items] == ["Apple", "banana", "zebra"]


@pytest.mark.asyncio
async def test_query_list_recommendations_rejects_empty_seed_list(monkeypatch):
    async def fake_generator(*args, **kwargs):
        raise AssertionError("generator should not be called for empty input")

    monkeypatch.setattr(
        "backend.services.recommendation_service.generate_recommendations_for_list",
        fake_generator,
    )

    with pytest.raises(BadRequestError) as exc:
        await get_recommendations_for_query_list_page(
            manga_ids=[],
            order_by="score",
            order_dir="desc",
            page=1,
            size=20,
            db=None,
        )

    assert exc.value.code == "RECOMMENDATION_SEED_EMPTY"


@pytest.mark.asyncio
async def test_query_list_recommendations_dedupes_preserving_order(monkeypatch):
    captured = {}

    async def fake_generator(manga_ids, db):
        captured["manga_ids"] = manga_ids

        return {
            "seed_total": 3,
            "seed_used": 2,
            "seed_truncated": False,
            "items": [],
        }

    monkeypatch.setattr(
        "backend.services.recommendation_service.generate_recommendations_for_list",
        fake_generator,
    )

    data = await get_recommendations_for_query_list_page(
        manga_ids=[10, 20, 10],
        order_by="score",
        order_dir="desc",
        page=1,
        size=20,
        db=None,
    )

    assert captured["manga_ids"] == [10, 20]
    assert data["seed_total"] == 3
    assert data["seed_used"] == 2
    assert data["seed_truncated"] is False
    assert data["items"] == []


@pytest.mark.asyncio
async def test_query_list_recommendations_paginates_after_sorting(monkeypatch):
    async def fake_generator(manga_ids, db):
        return {
            "seed_total": 1,
            "seed_used": 1,
            "seed_truncated": False,
            "items": [
                {"manga_id": 1, "title": "Low", "score": 1.0},
                {"manga_id": 2, "title": "High", "score": 9.0},
                {"manga_id": 3, "title": "Mid", "score": 5.0},
            ],
        }

    monkeypatch.setattr(
        "backend.services.recommendation_service.generate_recommendations_for_list",
        fake_generator,
    )

    data = await get_recommendations_for_query_list_page(
        manga_ids=[123],
        order_by="score",
        order_dir="desc",
        page=2,
        size=1,
        db=None,
    )

    assert data["total_results"] == 3
    assert data["page"] == 2
    assert data["size"] == 1
    assert data["items"] == [
        {"manga_id": 3, "title": "Mid", "score": 5.0}
    ]