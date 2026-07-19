from __future__ import annotations

from fastapi.testclient import TestClient

from .helpers import RegisteredUser, assert_error, register_and_login, register_user


def test_health_and_readiness_routes(client: TestClient) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json() == {"message": "MangaRecon API is running."}

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.json() == {"message": "MangaRecon API is ready."}


def test_protected_route_rejects_anonymous_request(client: TestClient) -> None:
    response = client.get("/profiles/me")
    assert_error(response, status_code=401)


def test_register_login_and_logout_cookie_flow(client: TestClient) -> None:
    user = RegisteredUser(
        email="auth-flow@example.com",
        username="auth_flow",
        displayname="Auth Flow",
    )

    created = register_user(client, user)
    assert created["email"] == user.email
    assert created["username"] == user.username
    assert created["displayname"] == user.displayname

    login = client.post(
        "/auth/jwt/login",
        data={"username": user.email, "password": user.password},
    )
    assert login.status_code == 204, login.text
    assert "auth" in client.cookies

    profile = client.get("/profiles/me")
    assert profile.status_code == 200, profile.text

    logout = client.post("/auth/jwt/logout")
    assert logout.status_code == 204, logout.text

    after_logout = client.get("/profiles/me")
    assert after_logout.status_code == 401


def test_duplicate_registration_maps_to_project_error_envelope(client: TestClient) -> None:
    user = RegisteredUser(
        email="duplicate@example.com",
        username="duplicate_one",
        displayname="Duplicate One",
    )
    register_user(client, user)

    response = client.post(
        "/auth/register",
        json={
            "email": user.email,
            "password": user.password,
            "username": "duplicate_two",
            "displayname": "Duplicate Two",
        },
    )
    assert_error(response, status_code=409, detail="AUTH_EMAIL_EXISTS")


def test_bad_login_credentials_map_to_project_error(client: TestClient) -> None:
    user = register_and_login(client, suffix="badlogin")
    client.post("/auth/jwt/logout")

    response = client.post(
        "/auth/jwt/login",
        data={"username": user.email, "password": "WrongPass123!"},
    )
    assert_error(response, status_code=401, detail="AUTH_INVALID_CREDENTIALS")


def test_registration_validation_uses_standard_error_envelope(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "password": "short",
            "username": "abc",
            "displayname": "abc",
        },
    )
    body = assert_error(response, status_code=422)
    assert body["message"] == "Validation error"
    assert isinstance(body["detail"], list)
