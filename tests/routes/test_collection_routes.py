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

@pytest.mark.asyncio
async def test_collections_pagination(async_client):
    # create 25 collections
    for i in range(25):
        r = await async_client.post("/collections/", json={"collection_name": f"c{i}", "description": "d"})
        assert r.status_code == 200, r.text

    # page 1 size 20 => 20 items
    p1 = await async_client.get("/collections/?page=1&size=20")
    assert p1.status_code == 200, p1.text
    body1 = p1.json()["data"]
    assert body1["total_results"] >= 25
    assert len(body1["items"]) == 20

    # page 2 size 20 => remaining 5 items (assuming exactly 25 exist in this isolated test DB)
    p2 = await async_client.get("/collections/?page=2&size=20")
    assert p2.status_code == 200, p2.text
    body2 = p2.json()["data"]
    assert len(body2["items"]) == 5


@pytest.mark.asyncio
async def test_update_collection_name_conflict_returns_409(async_client):
    c1 = await async_client.post("/collections/", json={"collection_name": "A", "description": "d"})
    assert c1.status_code == 200, c1.text
    id1 = c1.json()["data"]["collection_id"]

    c2 = await async_client.post("/collections/", json={"collection_name": "B", "description": "d"})
    assert c2.status_code == 200, c2.text
    id2 = c2.json()["data"]["collection_id"]

    # rename B -> A should conflict
    resp = await async_client.put(f"/collections/{id2}", json={"collection_name": "A"})
    assert resp.status_code == 409, resp.text

@pytest.mark.asyncio
async def test_add_manga_duplicate_returns_409(async_client, db_session):
    manga = await make_manga(db_session)

    # Create collection
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "DupAdd", "description": "d"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # First add => OK
    r1 = await async_client.post(
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert r1.status_code == 200, r1.text

    # Second add => 409
    r2 = await async_client.post(
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert r2.status_code == 409, r2.text

    body = r2.json()
    assert body["status"] == "error"


@pytest.mark.asyncio
async def test_remove_manga_missing_returns_404(async_client, db_session):
    manga = await make_manga(db_session)

    # Create collection
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "MissingRemove", "description": "d"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # Remove without ever adding => 404
    r = await async_client.request(
        "DELETE",
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert r.status_code == 404, r.text

    body = r.json()
    assert body["status"] == "error"


@pytest.mark.asyncio
async def test_remove_manga_twice_second_time_returns_404(async_client, db_session):
    manga = await make_manga(db_session)

    # Create collection
    resp = await async_client.post(
        "/collections/",
        json={"collection_name": "RemoveTwice", "description": "d"},
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["data"]["collection_id"]

    # Add manga
    add = await async_client.post(
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert add.status_code == 200, add.text

    # Remove once => 200
    rm1 = await async_client.request(
        "DELETE",
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert rm1.status_code == 200, rm1.text

    # Remove again => 404
    rm2 = await async_client.request(
        "DELETE",
        f"/collections/{cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert rm2.status_code == 404, rm2.text