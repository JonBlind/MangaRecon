from helpers import register_and_login, create_collection, create_test_manga


def add_manga_to_collection(client, collection_id: int, manga_id: int):
    response = client.post(
        f"/collections/{collection_id}/mangas",
        json={"manga_id": manga_id},
    )

    assert response.status_code == 200
    return response.json()["data"]


def test_collection_recommendations_require_auth(client):
    response = client.get("/recommendations/1")

    assert response.status_code == 401


def test_collection_recommendations_empty_collection_returns_400(client):
    register_and_login(client)
    collection = create_collection(client)

    response = client.get(f"/recommendations/{collection['collection_id']}")

    assert response.status_code == 400


def test_collection_recommendations_for_owned_collection(client):
    register_and_login(client)
    collection = create_collection(client)
    manga = create_test_manga()

    add_manga_to_collection(
        client,
        collection["collection_id"],
        manga["manga_id"],
    )

    response = client.get(f"/recommendations/{collection['collection_id']}")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert data["page"] == 1
    assert data["size"] == 20
    assert "total_results" in data
    assert "items" in data
    assert "seed_total" in data
    assert "seed_used" in data
    assert "seed_truncated" in data
    assert isinstance(data["items"], list)


def test_user_cannot_get_recommendations_for_another_users_collection(client):
    register_and_login(client)
    collection = create_collection(client)

    client.post("/auth/jwt/logout")

    register_and_login(client)

    response = client.get(f"/recommendations/{collection['collection_id']}")

    assert response.status_code == 404


def test_collection_recommendations_invalid_page_returns_422(client):
    register_and_login(client)
    collection = create_collection(client)

    response = client.get(
        f"/recommendations/{collection['collection_id']}",
        params={"page": 0},
    )

    assert response.status_code == 422


def test_collection_recommendations_invalid_size_returns_422(client):
    register_and_login(client)
    collection = create_collection(client)

    response = client.get(
        f"/recommendations/{collection['collection_id']}",
        params={"size": 101},
    )

    assert response.status_code == 422


def test_query_list_recommendations_empty_payload_returns_422(client):
    response = client.post(
        "/recommendations/query-list",
        json={"manga_ids": []},
    )

    assert response.status_code == 422


def test_query_list_recommendations_for_manga_ids(client):
    manga = create_test_manga()

    response = client.post(
        "/recommendations/query-list",
        json={"manga_ids": [manga["manga_id"]]},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert data["page"] == 1
    assert data["size"] == 20
    assert data["seed_total"] == 1
    assert data["seed_used"] == 1
    assert data["seed_truncated"] is False
    assert "total_results" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_query_list_recommendations_invalid_page_returns_422(client):
    manga = create_test_manga()

    response = client.post(
        "/recommendations/query-list",
        params={"page": 0},
        json={"manga_ids": [manga["manga_id"]]},
    )

    assert response.status_code == 422


def test_query_list_recommendations_invalid_size_returns_422(client):
    manga = create_test_manga()

    response = client.post(
        "/recommendations/query-list",
        params={"size": 101},
        json={"manga_ids": [manga["manga_id"]]},
    )

    assert response.status_code == 422