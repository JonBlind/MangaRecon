from tests.routes.helpers import register_and_login, create_test_manga


def test_rate_manga_requires_auth(client):
    manga = create_test_manga()

    response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 8.5,
        },
    )

    assert response.status_code == 401


def test_logged_in_user_can_create_rating(client):
    register_and_login(client)
    manga = create_test_manga()

    response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 8.5,
        },
    )

    assert response.status_code == 200

    rating = response.json()["data"]
    assert rating["manga_id"] == manga["manga_id"]
    assert float(rating["personal_rating"]) == 8.5


def test_logged_in_user_can_update_existing_rating(client):
    register_and_login(client)
    manga = create_test_manga()

    first_response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 7.0,
        },
    )
    assert first_response.status_code == 200

    update_response = client.put(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 9.0,
        },
    )

    assert update_response.status_code == 200

    rating = update_response.json()["data"]
    assert rating["manga_id"] == manga["manga_id"]
    assert float(rating["personal_rating"]) == 9.0


def test_logged_in_user_can_get_rating_for_manga(client):
    register_and_login(client)
    manga = create_test_manga()

    create_response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 8.0,
        },
    )
    assert create_response.status_code == 200

    response = client.get(
        "/ratings",
        params={"manga_id": manga["manga_id"]},
    )

    assert response.status_code == 200

    rating = response.json()["data"]
    assert rating["manga_id"] == manga["manga_id"]
    assert float(rating["personal_rating"]) == 8.0


def test_logged_in_user_can_list_own_ratings(client):
    register_and_login(client)
    manga = create_test_manga()

    create_response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 6.5,
        },
    )
    assert create_response.status_code == 200

    response = client.get("/ratings")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"

    ratings = body["data"]["items"]

    assert any(
        r["manga_id"] == manga["manga_id"]
        for r in ratings
    )


def test_logged_in_user_can_delete_rating(client):
    register_and_login(client)
    manga = create_test_manga()

    create_response = client.post(
        "/ratings",
        json={
            "manga_id": manga["manga_id"],
            "personal_rating": 7.5,
        },
    )
    assert create_response.status_code == 200

    delete_response = client.delete(
        f"/ratings/{manga['manga_id']}"
    )

    assert delete_response.status_code == 200

    list_response = client.get("/ratings")

    assert list_response.status_code == 200

    ratings = list_response.json()["data"]["items"]

    assert all(
        r["manga_id"] != manga["manga_id"]
        for r in ratings
    )


def test_rate_nonexistent_manga_returns_404(client):
    register_and_login(client)

    response = client.post(
        "/ratings",
        json={
            "manga_id": 999999999,
            "personal_rating": 8.0,
        },
    )

    assert response.status_code == 404


def test_get_missing_rating_returns_404(client):
    register_and_login(client)
    manga = create_test_manga()

    response = client.get(
        "/ratings",
        params={"manga_id": manga["manga_id"]},
    )

    assert response.status_code == 404


def test_delete_missing_rating_returns_404(client):
    register_and_login(client)
    manga = create_test_manga()

    response = client.delete(
        f"/ratings/{manga['manga_id']}"
    )

    assert response.status_code == 404