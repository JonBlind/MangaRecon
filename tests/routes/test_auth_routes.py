from tests.routes.helpers import unique_user_payload


def test_register_user_returns_created_user(client):
    payload = unique_user_payload()

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 201

    body = response.json()

    assert body["email"] == payload["email"]
    assert body["username"] == payload["username"]
    assert body["displayname"] == payload["displayname"]
    assert "id" in body
    assert "hashed_password" not in body


def test_register_rejects_short_password(client):
    payload = unique_user_payload()
    payload["password"] = "short"

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422


def test_register_rejects_short_username(client):
    payload = unique_user_payload()
    payload["username"] = "abc"

    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422


def test_login_sets_auth_cookie(client):
    payload = unique_user_payload()

    register_response = client.post(
        "/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert response.status_code == 204
    assert "auth" in response.cookies


def test_profiles_me_requires_auth(client):
    response = client.get("/profiles/me")

    assert response.status_code == 401


def test_logged_in_user_can_read_profiles_me(client):
    payload = unique_user_payload()

    register_response = client.post(
        "/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 204

    response = client.get("/profiles/me")

    assert response.status_code == 200

    body = response.json()
    user_data = body["data"]

    assert user_data["email"] == payload["email"]
    assert user_data["username"] == payload["username"]
    assert user_data["displayname"] == payload["displayname"]


def test_logout_clears_auth_cookie(client):
    payload = unique_user_payload()

    register_response = client.post(
        "/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 204

    authenticated_response = client.get("/profiles/me")
    assert authenticated_response.status_code == 200

    logout_response = client.post("/auth/jwt/logout")

    assert logout_response.status_code == 204

    me_response = client.get("/profiles/me")

    assert me_response.status_code == 401


def test_register_rejects_duplicate_email(client):
    payload = unique_user_payload()

    first_response = client.post(
        "/auth/register",
        json=payload,
    )
    assert first_response.status_code == 201

    second_payload = unique_user_payload()
    second_payload["email"] = payload["email"]

    second_response = client.post(
        "/auth/register",
        json=second_payload,
    )

    assert second_response.status_code in {400, 409}


def test_login_rejects_wrong_password(client):
    payload = unique_user_payload()

    register_response = client.post(
        "/auth/register",
        json=payload,
    )
    assert register_response.status_code == 201

    response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    payload = unique_user_payload()

    response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert response.status_code == 401


def test_expected_account_routes_are_registered(client):
    paths = client.app.openapi()["paths"]

    assert "/auth/register" in paths
    assert "/auth/jwt/login" in paths
    assert "/auth/jwt/logout" in paths

    assert "/auth/forgot-password" in paths
    assert "/auth/reset-password" in paths
    assert "/auth/request-verify-token" in paths
    assert "/auth/verify" in paths

    assert "/profiles/me" in paths
    assert "/users/me" not in paths


def test_generated_users_me_route_is_not_exposed(client):
    response = client.get("/users/me")

    assert response.status_code == 404