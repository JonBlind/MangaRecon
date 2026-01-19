import pytest
from tests.db.factories import make_manga
import tests.routes.conftest

@pytest.mark.asyncio
async def test_post_rating_creates(async_client, db_session):
    manga = await make_manga(db_session)

    resp = await async_client.post(
        "/ratings/",
        json={"manga_id": manga.manga_id, "personal_rating": 7.5},
    )
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["manga_id"] == manga.manga_id
    assert data["personal_rating"] == 7.5
    assert "created_at" in data

@pytest.mark.asyncio
async def test_get_ratings_list(async_client, db_session):
    manga = await make_manga(db_session)

    # create one rating
    await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 8.0})

    resp = await async_client.get("/ratings/?page=1&size=20")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["status"] == "success"
    payload = body["data"]
    assert payload["total_results"] >= 1
    assert any(item["manga_id"] == manga.manga_id for item in payload["items"])
