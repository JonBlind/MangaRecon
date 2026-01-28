import pytest
from tests.db.factories import make_manga

@pytest.mark.asyncio
async def test_metadata_genres_is_public(_raw_async_client):
    resp = await _raw_async_client.get("/metadata/genres?page=1&size=20")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert "items" in body["data"]


@pytest.mark.asyncio
async def test_metadata_tags_is_public(_raw_async_client):
    resp = await _raw_async_client.get("/metadata/tags?page=1&size=20")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert "items" in body["data"]


@pytest.mark.asyncio
async def test_metadata_demographics_is_public(_raw_async_client):
    resp = await _raw_async_client.get("/metadata/demographics?page=1&size=20")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert "items" in body["data"]

@pytest.mark.asyncio
async def test_query_list_recommendations_is_public(_raw_async_client, db_session):
    m1 = await make_manga(db_session)
    m2 = await make_manga(db_session)

    resp = await _raw_async_client.post(
        "/recommendations/query-list?page=1&size=20",
        json={"manga_ids": [m1.manga_id, m2.manga_id]},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    assert "items" in body["data"]
    assert "seed_total" in body["data"]
    assert "seed_used" in body["data"]
    assert "seed_truncated" in body["data"]