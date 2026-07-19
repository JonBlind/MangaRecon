from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from .helpers import (
    assert_error,
    assert_success,
    create_collection,
    register_and_login,
    seed_catalog,
)


def test_collection_crud_and_pagination(client: TestClient) -> None:
    register_and_login(client, suffix="collections")

    first = create_collection(client, name="First")
    second = create_collection(client, name="Second")
    assert first["collection_id"] != second["collection_id"]

    page_one = assert_success(
        client.get("/collections", params={"page": 1, "size": 1, "order": "asc"})
    )["data"]
    assert page_one["total_results"] == 2
    assert page_one["items"][0]["collection_name"] == "First"

    fetched = assert_success(
        client.get(f"/collections/{second['collection_id']}")
    )["data"]
    assert fetched["collection_name"] == "Second"

    updated = assert_success(
        client.put(
            f"/collections/{second['collection_id']}",
            json={"collection_name": "Renamed", "description": "Changed"},
        )
    )["data"]
    assert updated["collection_name"] == "Renamed"
    assert updated["description"] == "Changed"

    deleted = assert_success(
        client.delete(f"/collections/{first['collection_id']}")
    )["data"]
    assert deleted["collection_id"] == first["collection_id"]

    assert client.get(f"/collections/{first['collection_id']}").status_code == 404


def test_duplicate_collection_name_returns_conflict(client: TestClient) -> None:
    register_and_login(client, suffix="collectionconflict")
    create_collection(client, name="Duplicate")

    response = client.post(
        "/collections",
        json={"collection_name": "Duplicate", "description": None},
    )
    assert_error(response, status_code=409, detail="COLLECTION_NAME_CONFLICT")


def test_collection_validation_rejects_whitespace_name(client: TestClient) -> None:
    register_and_login(client, suffix="collectionvalidation")

    response = client.post(
        "/collections",
        json={"collection_name": "   ", "description": None},
    )
    assert_error(response, status_code=422)


def test_collection_ownership_isolated_between_users(
    client_factory,
) -> None:
    owner = client_factory()
    other = client_factory()
    register_and_login(owner, suffix="owner")
    register_and_login(other, suffix="other")

    collection = create_collection(owner, name="Private")

    read = other.get(f"/collections/{collection['collection_id']}")
    update = other.put(
        f"/collections/{collection['collection_id']}",
        json={"collection_name": "Stolen"},
    )
    delete = other.delete(f"/collections/{collection['collection_id']}")

    assert_error(read, status_code=404, detail="COLLECTION_NOT_FOUND")
    assert_error(update, status_code=404, detail="COLLECTION_NOT_FOUND")
    assert_error(delete, status_code=404, detail="COLLECTION_NOT_FOUND")


def test_single_add_list_duplicate_and_remove_manga_flow(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="membership")
    catalog = seed_catalog(manga_write_engine)
    collection = create_collection(client)
    collection_id = collection["collection_id"]

    added = assert_success(
        client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": catalog.seed_manga_id},
        )
    )["data"]
    assert added == {
        "collection_id": collection_id,
        "manga_id": catalog.seed_manga_id,
    }

    listed = assert_success(
        client.get(f"/collections/{collection_id}/mangas")
    )["data"]
    assert listed["total_results"] == 1
    assert listed["items"][0]["manga_id"] == catalog.seed_manga_id
    assert listed["items"][0]["title"] == "Alpha Quest"

    duplicate = client.post(
        f"/collections/{collection_id}/mangas",
        json={"manga_id": catalog.seed_manga_id},
    )
    assert duplicate.status_code == 409

    removed = assert_success(
        client.request(
            "DELETE",
            f"/collections/{collection_id}/mangas",
            json={"manga_id": catalog.seed_manga_id},
        )
    )["data"]
    assert removed["manga_id"] == catalog.seed_manga_id

    after = assert_success(
        client.get(f"/collections/{collection_id}/mangas")
    )["data"]
    assert after["total_results"] == 0


def test_add_missing_manga_proves_manga_read_dependency_is_used(
    client: TestClient,
) -> None:
    register_and_login(client, suffix="missingmanga")
    collection = create_collection(client)

    response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": 999999},
    )
    assert_error(response, status_code=404, detail="MANGA_NOT_FOUND")


def test_bulk_add_reports_added_duplicate_and_missing_rows(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="bulk")
    catalog = seed_catalog(manga_write_engine)
    collection = create_collection(client)
    collection_id = collection["collection_id"]

    first = assert_success(
        client.post(
            f"/collections/{collection_id}/mangas/bulk",
            json={
                "manga_ids": [catalog.seed_manga_id, catalog.similar_manga_id, 999999]
            },
        )
    )["data"]
    assert first["added_count"] == 2
    assert first["failed_count"] == 1
    assert first["failed"] == [{"manga_id": 999999, "reason": "MANGA_NOT_FOUND"}]

    second = assert_success(
        client.post(
            f"/collections/{collection_id}/mangas/bulk",
            json={"manga_ids": [catalog.seed_manga_id]},
        )
    )["data"]
    assert second["added_count"] == 0
    assert second["failed"] == [
        {"manga_id": catalog.seed_manga_id, "reason": "ALREADY_EXISTS"}
    ]
