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


def test_public_query_list_recommendations_exclude_seed_and_rank_similar_candidate(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    catalog = seed_catalog(manga_write_engine)

    response = client.post(
        "/recommendations/query-list",
        params={"order_by": "score", "order_dir": "desc"},
        json={"manga_ids": [catalog.seed_manga_id]},
    )
    data = assert_success(response)["data"]

    assert data["seed_total"] == 1
    assert data["seed_used"] == 1
    assert data["seed_truncated"] is False
    ids = [item["manga_id"] for item in data["items"]]
    assert catalog.seed_manga_id not in ids
    assert catalog.similar_manga_id in ids


def test_public_query_list_recommendations_deduplicate_seeds(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    catalog = seed_catalog(manga_write_engine)

    data = assert_success(
        client.post(
            "/recommendations/query-list",
            json={
                "manga_ids": [
                    catalog.seed_manga_id,
                    catalog.seed_manga_id,
                    catalog.seed_manga_id,
                ]
            },
        )
    )["data"]

    assert data["seed_total"] == 1
    assert data["seed_used"] == 1


def test_public_query_list_rejects_empty_seed_list(client: TestClient) -> None:
    response = client.post("/recommendations/query-list", json={"manga_ids": []})
    # Pydantic rejects it before the service because the schema has min_length=1.
    assert_error(response, status_code=422)


def test_collection_recommendation_full_http_and_database_flow(
    client: TestClient,
    manga_write_engine: Engine,
) -> None:
    register_and_login(client, suffix="collectionrecs")
    catalog = seed_catalog(manga_write_engine)
    collection = create_collection(client, name="Recommendation Seeds")
    collection_id = collection["collection_id"]

    assert_success(
        client.post(
            f"/collections/{collection_id}/mangas",
            json={"manga_id": catalog.seed_manga_id},
        )
    )

    data = assert_success(
        client.get(
            f"/recommendations/{collection_id}",
            params={"order_by": "score", "order_dir": "desc", "page": 1, "size": 10},
        )
    )["data"]

    assert data["seed_total"] == 1
    assert data["seed_used"] == 1
    ids = [item["manga_id"] for item in data["items"]]
    assert catalog.seed_manga_id not in ids
    assert catalog.similar_manga_id in ids


def test_collection_recommendations_require_owned_collection(
    client_factory,
    manga_write_engine: Engine,
) -> None:
    seed_catalog(manga_write_engine)
    owner = client_factory()
    other = client_factory()
    register_and_login(owner, suffix="recowner")
    register_and_login(other, suffix="recother")

    collection = create_collection(owner, name="Owner Seeds")

    response = other.get(f"/recommendations/{collection['collection_id']}")
    assert_error(response, status_code=404, detail="COLLECTION_NOT_FOUND")


def test_collection_recommendations_reject_empty_collection(client: TestClient) -> None:
    register_and_login(client, suffix="emptyrecs")
    collection = create_collection(client, name="Empty")

    response = client.get(f"/recommendations/{collection['collection_id']}")
    assert_error(response, status_code=400, detail="RECOMMENDATION_SEED_EMPTY")
