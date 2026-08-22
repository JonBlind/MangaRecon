from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
from fastapi_users.jwt import generate_jwt

from backend.auth import user_manager
from backend.rate_limit.account import AccountRateLimitDecision
from backend.auth.user_manager import UserManager
from tests.routes.helpers import unique_user_payload, verify_registered_user


def request_password_reset_token(client, monkeypatch, email):
    captured: dict[str, str] = {}

    async def capture_reset_email(*, recipient, token):
        captured["recipient"] = recipient
        captured["token"] = token

    monkeypatch.setattr(
        user_manager,
        "send_password_reset_email",
        capture_reset_email,
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": email},
    )

    assert response.status_code == 202
    assert captured["recipient"] == email
    return captured["token"]


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
    assert body["is_verified"] is False
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
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

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
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

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
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

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
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

    response = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


def test_login_rejects_unverified_user(client):
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

    assert response.status_code == 403
    assert response.json()["detail"] == "AUTH_NOT_VERIFIED"
    assert "auth" not in response.cookies


def test_request_verify_token_does_not_reveal_unknown_email(client):
    response = client.post(
        "/auth/request-verify-token",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 202


def test_forgot_password_does_not_reveal_unknown_email(
    client,
    monkeypatch,
):
    send_email = AsyncMock()
    monkeypatch.setattr(
        user_manager,
        "send_password_reset_email",
        send_email,
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": "unknown@example.com"},
    )

    assert response.status_code == 202
    send_email.assert_not_awaited()


def test_forgot_password_stays_generic_when_delivery_fails(
    client,
    monkeypatch,
):
    payload = unique_user_payload()
    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201

    send_email = AsyncMock(
        side_effect=user_manager.EmailDeliveryError("delivery failed")
    )
    monkeypatch.setattr(
        user_manager,
        "send_password_reset_email",
        send_email,
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": payload["email"]},
    )

    assert response.status_code == 202
    send_email.assert_awaited_once()


def test_forgot_password_stays_generic_when_recipient_is_limited(
    client,
    monkeypatch,
):
    payload = unique_user_payload()
    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201

    check_recipient = AsyncMock(
        return_value=AccountRateLimitDecision(
            allowed=False,
            retry_after=60,
        )
    )
    send_email = AsyncMock()
    monkeypatch.setattr(
        user_manager.account_rate_limiter,
        "check_recipient",
        check_recipient,
    )
    monkeypatch.setattr(
        user_manager,
        "send_password_reset_email",
        send_email,
    )

    response = client.post(
        "/auth/forgot-password",
        json={"email": payload["email"]},
    )

    assert response.status_code == 202
    check_recipient.assert_awaited_once_with(payload["email"])
    send_email.assert_not_awaited()


def test_password_reset_flow_validates_and_consumes_token(
    client,
    monkeypatch,
):
    payload = unique_user_payload()
    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201
    verify_registered_user(
        client,
        user_id=register_response.json()["id"],
        email=payload["email"],
    )

    token = request_password_reset_token(
        client,
        monkeypatch,
        payload["email"],
    )

    validation_response = client.get(
        "/auth/reset-password",
        params={"token": token},
    )
    assert validation_response.status_code == 204

    short_password_response = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "short"},
    )
    assert short_password_response.status_code == 400
    assert short_password_response.json()["detail"] == "AUTH_PASSWORD_INVALID"

    reset_response = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "newpassword123"},
    )
    assert reset_response.status_code == 200

    reused_validation_response = client.get(
        "/auth/reset-password",
        params={"token": token},
    )
    assert reused_validation_response.status_code == 400
    assert reused_validation_response.json()["detail"] == "AUTH_RESET_INVALID"

    reused_reset_response = client.post(
        "/auth/reset-password",
        json={"token": token, "password": "anotherpassword123"},
    )
    assert reused_reset_response.status_code == 400
    assert reused_reset_response.json()["detail"] == "AUTH_RESET_INVALID"

    old_password_login = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": payload["password"],
        },
    )
    assert old_password_login.status_code == 401

    new_password_login = client.post(
        "/auth/jwt/login",
        data={
            "username": payload["email"],
            "password": "newpassword123",
        },
    )
    assert new_password_login.status_code == 204


def test_password_reset_validation_rejects_malformed_token(client):
    response = client.get(
        "/auth/reset-password",
        params={"token": "not-a-jwt"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "AUTH_RESET_INVALID"


def test_password_reset_validation_rejects_expired_wrong_purpose_and_unknown_user(
    client,
    monkeypatch,
):
    payload = unique_user_payload()
    register_response = client.post("/auth/register", json=payload)
    assert register_response.status_code == 201

    token = request_password_reset_token(
        client,
        monkeypatch,
        payload["email"],
    )
    token_payload = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
    )

    expired_token = generate_jwt(
        token_payload,
        UserManager.reset_password_token_secret,
        -1,
    )
    wrong_purpose_token = generate_jwt(
        {
            "sub": register_response.json()["id"],
            "email": payload["email"],
            "aud": UserManager.verification_token_audience,
        },
        UserManager.verification_token_secret,
        60,
    )
    unknown_user_payload = {
        **token_payload,
        "sub": str(uuid4()),
    }
    unknown_user_token = generate_jwt(
        unknown_user_payload,
        UserManager.reset_password_token_secret,
        60,
    )

    for invalid_token in (
        expired_token,
        wrong_purpose_token,
        unknown_user_token,
    ):
        response = client.get(
            "/auth/reset-password",
            params={"token": invalid_token},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "AUTH_RESET_INVALID"


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
    assert "get" in paths["/auth/reset-password"]
    assert "post" in paths["/auth/reset-password"]
    assert "/auth/request-verify-token" in paths
    assert "/auth/verify" in paths

    assert "/profiles/me" in paths
    assert "/users/me" not in paths


def test_generated_users_me_route_is_not_exposed(client):
    response = client.get("/users/me")

    assert response.status_code == 404
