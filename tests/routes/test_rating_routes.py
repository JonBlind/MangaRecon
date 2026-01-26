import pytest
from tests.db.factories import make_manga

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

@pytest.mark.asyncio
async def test_rate_manga_rejects_out_of_range(async_client, db_session):
    manga = await make_manga(db_session)

    resp = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": -0.5})
    assert resp.status_code in (400, 422), resp.text

    resp = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 10.5})
    assert resp.status_code in (400, 422), resp.text


@pytest.mark.asyncio
async def test_rate_manga_rejects_not_half_step(async_client, db_session):
    manga = await make_manga(db_session)

    # Not a 0.5 increment
    resp = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 7.3})
    assert resp.status_code in (400, 422), resp.text


@pytest.mark.asyncio
async def test_rate_manga_accepts_boundaries(async_client, db_session):
    manga = await make_manga(db_session)

    resp = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 0.0})
    assert resp.status_code == 200, resp.text

    resp = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 10.0})
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_rate_manga_upserts_existing_rating(async_client, db_session):
    manga = await make_manga(db_session)

    resp1 = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 6.0})
    assert resp1.status_code == 200, resp1.text

    resp2 = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 8.5})
    assert resp2.status_code == 200, resp2.text

    # Verify latest value via GET /ratings/?manga_id=...
    resp3 = await async_client.get(f"/ratings/?manga_id={manga.manga_id}")
    assert resp3.status_code == 200, resp3.text
    body = resp3.json()
    assert body["status"] == "success"
    assert body["data"]["personal_rating"] == 8.5


@pytest.mark.asyncio
async def test_post_rating_missing_manga_returns_404(async_client):
    resp = await async_client.post("/ratings/", json={"manga_id": 999999999, "personal_rating": 7.5})
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_rating_by_manga_id_missing_returns_404(async_client):
    resp = await async_client.get("/ratings/?manga_id=999999999")
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_ratings_list_shape(async_client):
    resp = await async_client.get("/ratings/?page=1&size=20")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success", body

    data = body["data"]
    assert "total_results" in data
    assert "page" in data
    assert "size" in data
    assert "items" in data
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_ratings_list_is_user_scoped(async_client, async_client_other_user, db_session):
    manga = await make_manga(db_session)

    # user A rates
    r1 = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 8.0})
    assert r1.status_code == 200, r1.text

    # user B lists ratings - should NOT see user A's rating
    r2 = await async_client_other_user.get("/ratings/?page=1&size=50")
    assert r2.status_code == 200, r2.text
    items = r2.json()["data"]["items"]
    assert all(item["manga_id"] != manga.manga_id for item in items)


@pytest.mark.asyncio
async def test_get_rating_by_manga_id_is_user_scoped(async_client, async_client_other_user, db_session):
    manga = await make_manga(db_session)

    # user A rates
    r1 = await async_client.post("/ratings/", json={"manga_id": manga.manga_id, "personal_rating": 7.5})
    assert r1.status_code == 200, r1.text

    # user B tries to fetch by manga_id - should be 404 (no rating for them)
    r2 = await async_client_other_user.get(f"/ratings/?manga_id={manga.manga_id}")
    assert r2.status_code == 404, r2.text