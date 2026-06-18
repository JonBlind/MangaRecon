from tests.backend.routes.helpers import register_and_login, create_collection

def test_create_collection_requires_auth(client):
    response = client.post(
        "/collections",
        json={
            "collection_name": "Favorites",
            "description": "My favorite manga",
        },
    )

    assert response.status_code == 401


def test_logged_in_user_can_create_collection(client):
    register_and_login(client)

    collection = create_collection(client)

    assert collection["collection_name"] == "Favorites"
    assert collection["description"] == "My favorite manga"
    assert "collection_id" in collection
    assert "created_at" in collection


def test_logged_in_user_can_list_own_collections(client):
    register_and_login(client)
    created = create_collection(client, name="Reading List")

    response = client.get("/collections")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    data = body["data"]
    assert data["total_results"] >= 1
    assert data["page"] == 1
    assert "items" in data

    collection_names = [item["collection_name"] for item in data["items"]]
    assert created["collection_name"] in collection_names


def test_logged_in_user_can_get_collection_by_id(client):
    register_and_login(client)
    created = create_collection(client, name="Details Test")

    response = client.get(f"/collections/{created['collection_id']}")

    assert response.status_code == 200

    collection = response.json()["data"]
    assert collection["collection_id"] == created["collection_id"]
    assert collection["collection_name"] == "Details Test"


def test_logged_in_user_can_update_collection(client):
    register_and_login(client)
    created = create_collection(client, name="Before Update")

    response = client.put(
        f"/collections/{created['collection_id']}",
        json={
            "collection_name": "After Update",
            "description": "Updated description",
        },
    )

    assert response.status_code == 200

    collection = response.json()["data"]
    assert collection["collection_id"] == created["collection_id"]
    assert collection["collection_name"] == "After Update"
    assert collection["description"] == "Updated description"


def test_logged_in_user_can_delete_collection(client):
    register_and_login(client)
    created = create_collection(client, name="Delete Me")

    delete_response = client.delete(f"/collections/{created['collection_id']}")

    assert delete_response.status_code == 200
    assert delete_response.json()["data"]["collection_id"] == created["collection_id"]

    get_response = client.get(f"/collections/{created['collection_id']}")
    assert get_response.status_code == 404


def test_create_collection_rejects_blank_name(client):
    register_and_login(client)

    response = client.post(
        "/collections",
        json={
            "collection_name": "   ",
            "description": "Invalid name",
        },
    )

    assert response.status_code == 422


def test_user_cannot_access_another_users_collection(client):
    register_and_login(client)
    created = create_collection(client, name="Private Collection")

    client.post("/auth/jwt/logout")

    register_and_login(client)

    response = client.get(f"/collections/{created['collection_id']}")

    assert response.status_code == 404

def test_duplicate_collection_names_not_allowed(client):
    register_and_login(client)

    create_collection(client, name="Favorites")

    response = client.post(
        "/collections",
        json={
            "collection_name": "Favorites",
            "description": "Duplicate",
        },
    )

    assert response.status_code in {400, 409}