import pytest
from tests.db.factories import make_manga
from tests.db.factories import make_collection

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
async def test_collections_list_is_ordered_by_id_desc(async_client):
    created_ids = []

    for i in range(3):
        r = await async_client.post(
            "/collections/",
            json={"collection_name": f"ord{i}", "description": "d"},
        )
        assert r.status_code == 200, r.text
        created_ids.append(r.json()["data"]["collection_id"])

    resp = await async_client.get("/collections/?page=1&size=10")
    assert resp.status_code == 200, resp.text

    items = _unwrap_items(resp.json()["data"])
    ids = [c["collection_id"] for c in items]

    # Only assert about the collections we just created (they should appear first in desc order)
    expected = sorted(created_ids, reverse=True)
    assert ids[:3] == expected

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

@pytest.mark.asyncio
async def test_add_manga_to_missing_collection_returns_404(async_client, db_session):
    manga = await make_manga(db_session)

    missing_cid = 999999999
    resp = await async_client.post(
        f"/collections/{missing_cid}/mangas",
        json={"manga_id": manga.manga_id},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_mangas_in_missing_collection_returns_404(async_client):
    missing_cid = 999999999
    resp = await async_client.get(f"/collections/{missing_cid}/mangas?page=1&size=20")
    assert resp.status_code == 404, resp.text

@pytest.mark.asyncio
async def test_other_user_cannot_get_collection_by_id_returns_404(async_client, async_client_other_user):
    c = await async_client.post("/collections/", json={"collection_name": "Private", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    r = await async_client_other_user.get(f"/collections/{cid}")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_other_user_cannot_update_collection_returns_404(async_client, async_client_other_user):
    c = await async_client.post("/collections/", json={"collection_name": "ToRename", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    r = await async_client_other_user.put(f"/collections/{cid}", json={"collection_name": "Hacked"})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_other_user_cannot_delete_collection_returns_404(async_client, async_client_other_user):
    c = await async_client.post("/collections/", json={"collection_name": "ToDelete", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    r = await async_client_other_user.delete(f"/collections/{cid}")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_other_user_cannot_add_manga_to_collection_returns_404(async_client, async_client_other_user, db_session):
    manga = await make_manga(db_session)

    c = await async_client.post("/collections/", json={"collection_name": "AOnly", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    r = await async_client_other_user.post(f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_other_user_cannot_list_mangas_in_collection_returns_404(async_client, async_client_other_user, db_session):
    manga = await make_manga(db_session)

    c = await async_client.post("/collections/", json={"collection_name": "AListOnly", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    add = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert add.status_code == 200, add.text

    r = await async_client_other_user.get(f"/collections/{cid}/mangas?page=1&size=20")
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_other_user_cannot_remove_manga_from_collection_returns_404(async_client, async_client_other_user, db_session):
    manga = await make_manga(db_session)

    c = await async_client.post("/collections/", json={"collection_name": "ARemoveOnly", "description": "d"})
    assert c.status_code == 200, c.text
    cid = c.json()["data"]["collection_id"]

    add = await async_client.post(f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert add.status_code == 200, add.text

    r = await async_client_other_user.request("DELETE", f"/collections/{cid}/mangas", json={"manga_id": manga.manga_id})
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_get_mangas_in_collection_order_desc(async_client, db_session):
    cr = await async_client.post(
        "/collections/",
        json={"collection_name": "order-desc", "description": "d"},
    )
    assert cr.status_code == 200, cr.text
    collection_id = cr.json()["data"]["collection_id"]

    m1 = await make_manga(db_session, title="m1")
    m2 = await make_manga(db_session, title="m2")
    m3 = await make_manga(db_session, title="m3")

    for m in (m1, m2, m3):
        r = await async_client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": m.manga_id},
        )
        assert r.status_code == 200, r.text

    resp = await async_client.get(
        f"/collections/{collection_id}/mangas?order=desc&page=1&size=20"
    )
    assert resp.status_code == 200, resp.text
    items = _unwrap_items(resp.json()["data"])
    ids = [x["manga_id"] for x in items]

    assert ids == sorted(ids, reverse=True)


@pytest.mark.asyncio
async def test_get_mangas_in_collection_order_asc(async_client, db_session):
    cr = await async_client.post(
        "/collections/",
        json={"collection_name": "order-asc", "description": "d"},
    )
    assert cr.status_code == 200, cr.text
    collection_id = cr.json()["data"]["collection_id"]

    m1 = await make_manga(db_session, title="a1")
    m2 = await make_manga(db_session, title="a2")
    m3 = await make_manga(db_session, title="a3")

    for m in (m1, m2, m3):
        r = await async_client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": m.manga_id},
        )
        assert r.status_code == 200, r.text

    resp = await async_client.get(
        f"/collections/{collection_id}/mangas?order=asc&page=1&size=20"
    )
    assert resp.status_code == 200, resp.text
    items = _unwrap_items(resp.json()["data"])
    ids = [x["manga_id"] for x in items]

    assert ids == sorted(ids)

@pytest.mark.asyncio
async def test_get_collections_order_desc(async_client):
    # create 3 collections
    ids = []
    for i in range(3):
        r = await async_client.post("/collections/", json={"collection_name": f"d{i}", "description": "d"})
        ids.append(r.json()["data"]["collection_id"])

    resp = await async_client.get("/collections/?order=desc&page=1&size=10")
    items = resp.json()["data"]["items"]
    got = [c["collection_id"] for c in items][:3]
    assert got == sorted(ids, reverse=True)


@pytest.mark.asyncio
async def test_get_collections_order_asc(async_client):
    ids = []
    for i in range(3):
        r = await async_client.post("/collections/", json={"collection_name": f"a{i}", "description": "d"})
        ids.append(r.json()["data"]["collection_id"])

    resp = await async_client.get("/collections/?order=asc&page=1&size=10")
    items = resp.json()["data"]["items"]
    got = [c["collection_id"] for c in items][:3]
    assert got == sorted(ids)