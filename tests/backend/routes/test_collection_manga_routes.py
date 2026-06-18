from helpers import register_and_login, create_collection, create_test_manga

def test_add_manga_to_collection_requires_auth(client):
    manga = create_test_manga()

    response = client.post(
        "/collections/1/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code == 401


def test_logged_in_user_can_add_manga_to_collection(client):
    register_and_login(client)
    collection = create_collection(client)
    manga = create_test_manga()

    response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code == 200


def test_duplicate_manga_add_is_rejected(client):
    register_and_login(client)
    collection = create_collection(client)
    manga = create_test_manga()

    client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code in {400, 409}


def test_remove_manga_from_collection(client):
    register_and_login(client)
    collection = create_collection(client)
    manga = create_test_manga()

    add_response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )
    assert add_response.status_code == 200

    response = client.request(
        "DELETE",
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code == 200
    assert response.json()["data"]["manga_id"] == manga["manga_id"]

def test_remove_nonexistent_manga_from_collection(client):
    register_and_login(client)
    collection = create_collection(client)
    manga = create_test_manga()

    response = client.request(
        "DELETE",
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code in {404, 400}

def test_user_cannot_add_manga_to_another_users_collection(client):
    register_and_login(client)

    collection = create_collection(client)
    manga = create_test_manga()

    client.post("/auth/jwt/logout")

    register_and_login(client)

    response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": manga["manga_id"]},
    )

    assert response.status_code in {403, 404}

def test_add_nonexistent_manga_to_collection(client):
    register_and_login(client)

    collection = create_collection(client)

    response = client.post(
        f"/collections/{collection['collection_id']}/mangas",
        json={"manga_id": 999999999},
    )

    assert response.status_code == 404