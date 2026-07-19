from __future__ import annotations

from fastapi.testclient import TestClient

from .helpers import assert_error, assert_success, login_user, register_and_login


def test_get_and_update_profile_persist_across_requests(client: TestClient) -> None:
    user = register_and_login(client, suffix="profile")

    initial = assert_success(client.get("/profiles/me"))["data"]
    assert initial["email"] == user.email
    assert initial["username"] == user.username
    assert initial["displayname"] == user.displayname

    updated = assert_success(
        client.patch("/profiles/me", json={"displayname": "Updated Display"})
    )["data"]
    assert updated["displayname"] == "Updated Display"

    reread = assert_success(client.get("/profiles/me"))["data"]
    assert reread["displayname"] == "Updated Display"


def test_username_only_patch_currently_applies_no_change(client: TestClient) -> None:
    user = register_and_login(client, suffix="usernamepatch")

    body = assert_success(
        client.patch("/profiles/me", json={"username": "new_username"})
    )
    assert body["message"] == "No changes applied"
    assert body["data"]["username"] == user.username


def test_profile_rejects_email_change(client: TestClient) -> None:
    register_and_login(client, suffix="emailpatch")

    response = client.patch("/profiles/me", json={"email": "changed@example.com"})
    assert_error(response, status_code=403, detail="PROFILE_FIELD_FORBIDDEN")


def test_change_password_invalidates_old_password_and_accepts_new_one(client: TestClient) -> None:
    user = register_and_login(client, suffix="password")
    new_password = "NewValidPass123!"

    changed = assert_success(
        client.post(
            "/profiles/me/change-password",
            json={
                "current_password": user.password,
                "new_password": new_password,
            },
        )
    )
    assert changed["message"] == "Password changed successfully"

    logout = client.post("/auth/jwt/logout")
    assert logout.status_code == 204

    old_login = client.post(
        "/auth/jwt/login",
        data={"username": user.email, "password": user.password},
    )
    assert_error(old_login, status_code=401, detail="AUTH_INVALID_CREDENTIALS")

    user_with_new_password = type(user)(
        email=user.email,
        username=user.username,
        displayname=user.displayname,
        password=new_password,
    )
    login_user(client, user_with_new_password)
    assert client.get("/profiles/me").status_code == 200


def test_change_password_rejects_wrong_current_password(client: TestClient) -> None:
    register_and_login(client, suffix="wrongpassword")

    response = client.post(
        "/profiles/me/change-password",
        json={
            "current_password": "DefinitelyWrong123!",
            "new_password": "AnotherValid123!",
        },
    )
    assert_error(response, status_code=400, detail="CURRENT_PASSWORD_INCORRECT")
