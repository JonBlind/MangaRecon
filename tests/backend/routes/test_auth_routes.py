from tests.backend.routes.helpers import unique_user_payload

def test_register_user_returns_created_user(client):
    payload = unique_user_payload()

    response = client.post("/auth/register", json=payload)

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

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_rejects_short_username(client):
    payload = unique_user_payload()
    payload["username"] = "abc"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_login_sets_auth_cookie(client):
    payload = unique_user_payload()
    client.post("/auth/register", json=payload)

    response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert response.status_code == 204
    assert "auth" in response.cookies


def test_users_me_requires_auth(client):
    response = client.get("/users/me")

    assert response.status_code == 401


def test_logged_in_user_can_read_users_me(client):
    payload = unique_user_payload()
    client.post("/auth/register", json=payload)

    login_response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 204

    response = client.get("/users/me")

    assert response.status_code == 200

    body = response.json()
    assert body["email"] == payload["email"]
    assert body["username"] == payload["username"]
    assert body["displayname"] == payload["displayname"]

def test_logout_clears_auth_cookie(client):
    payload = unique_user_payload()
    client.post("/auth/register", json=payload)

    login_response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )

    assert login_response.status_code == 204

    logout_response = client.post("/auth/jwt/logout")

    assert logout_response.status_code == 204

    me_response = client.get("/users/me")
    assert me_response.status_code == 401