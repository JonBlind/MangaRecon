import pytest
from tests.db.factories import make_manga


def _unwrap_items(data):
    # collections list / manga list endpoints return paginated dicts
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data


@pytest.mark.asyncio
async def test_create_collection_and_get_by_id(async_client):
    payload = {
        "collection_name": "Favorites",
        "description": "My top picks",  # must be non-empty
    }

    resp = await async_client.post("/collections/", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success", body

    created = body["data"]
    assert "collection_id" in created
    cid = created["collection_id"]

    # Read back
    resp2 = await async_client.get(f"/collections/{cid}")
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["status"] == "success", body2

    got = body2["data"]
    assert got["collection_id"] == cid
    assert got["collection_name"] == payload["collection_name"]
    assert got["description"] == payload["description"]


@pytest.mark.asyncio
async def test_get_users_collection_includes_created(async_client):
    # Create (description must be non-empty)
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "To Read", "description": "queue"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # List
    resp2 = await async_client.get("/collections/?page=1&size=20")
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["status"] == "success", body2

    payload = body2["data"]
    items = _unwrap_items(payload)
    assert any(c["collection_id"] == cid for c in items)


@pytest.mark.asyncio
async def test_update_collection_persists(async_client):
    # Create
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "Temp", "description": "old"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # Update (PUT)
    update_payload = {
        "collection_name": "Renamed",
        "description": "new",  # keep non-empty
    }
    resp2 = await async_client.put(f"/collections/{cid}", json=update_payload)
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["status"] == "success", body2

    # Read back
    resp3 = await async_client.get(f"/collections/{cid}")
    assert resp3.status_code == 200, resp3.text
    got = resp3.json()["data"]
    assert got["collection_name"] == "Renamed"
    assert got["description"] == "new"


@pytest.mark.asyncio
async def test_delete_collection_removes_it(async_client):
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "DeleteMe", "description": "bye"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    resp2 = await async_client.delete(f"/collections/{cid}")
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "success"

    resp3 = await async_client.get(f"/collections/{cid}")
    assert resp3.status_code == 404, resp3.text


@pytest.mark.asyncio
async def test_add_and_get_manga_in_collection(async_client, db_session):
    manga = await make_manga(db_session)

    # Create collection
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "WithManga", "description": "has stuff"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # Add manga
    resp2 = await async_client.post(
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "success"

    # List mangas in collection
    resp3 = await async_client.get(f"/collections/{cid}/mangas?page=1&size=50")
    assert resp3.status_code == 200, resp3.text
    body3 = resp3.json()
    assert body3["status"] == "success", body3

    items = _unwrap_items(body3["data"])
    assert any(item["manga_id"] == manga.manga_id for item in items)


@pytest.mark.asyncio
async def test_remove_manga_from_collection(async_client, db_session):
    manga = await make_manga(db_session)

    # Create collection
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "RemoveManga", "description": "temp"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # Add manga
    resp2 = await async_client.post(
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert resp2.status_code == 200, resp2.text

    # Remove manga (your route expects a JSON body)
    resp3 = await async_client.request(
        "DELETE",
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert resp3.status_code == 200, resp3.text
    assert resp3.json()["status"] == "success"

    # Verify removed
    resp4 = await async_client.get(f"/collections/{cid}/mangas?page=1&size=50")
    assert resp4.status_code == 200, resp4.text
    items = _unwrap_items(resp4.json()["data"])
    assert all(item["manga_id"] != manga.manga_id for item in items)