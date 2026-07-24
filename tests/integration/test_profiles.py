from __future__ import annotations
from fastapi.testclient import TestClient
from .helpers import assert_error, assert_success, login_user, make_user, register_and_login, register_user
import pytest

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


def test_username_update_persists_across_requests(client: TestClient) -> None:
    user = register_and_login(client, suffix="usernamepatch")

    assert user.username != "new_username"

    body = assert_success(
        client.patch(
            "/profiles/me",
            json={"username": "new_username"},
        )
    )

    assert body["message"] == "Profile updated successfully"
    assert body["data"]["username"] == "new_username"

    reread = assert_success(
        client.get("/profiles/me")
    )["data"]

    assert reread["username"] == "new_username"


def test_profile_rejects_email_change(client: TestClient) -> None:
    register_and_login(client, suffix="emailpatch")

    response = client.patch("/profiles/me", json={"email": "changed@example.com"})

    assert response.status_code == 422

    body = response.json()

    assert body["status"] == "error"
    assert body["data"] == {}
    assert body["message"] == "Validation error"

    assert any(
        error.get("type") == "extra_forbidden"
        and error.get("loc") == ["body", "email"]
        for error in body["detail"]
    )


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

def test_profile_rejects_password_change(client: TestClient) -> None:
    register_and_login(client, suffix="passwordpatch")

    response = client.patch(
        "/profiles/me",
        json={"password": "AnotherValidPass123!"},
    )

    assert response.status_code == 422

    body = response.json()

    assert body["status"] == "error"
    assert body["data"] == {}
    assert body["message"] == "Validation error"

    assert any(
        error.get("type") == "extra_forbidden"
        and error.get("loc") == ["body", "password"]
        for error in body["detail"]
    )

@pytest.mark.parametrize(
    "field",
    [
        "username",
        "displayname",
    ],
)
def test_profile_rejects_explicit_null_fields(
    client: TestClient,
    field: str,
) -> None:
    register_and_login(
        client,
        suffix=f"null_{field}",
    )

    response = client.patch(
        "/profiles/me",
        json={field: None},
    )

    assert response.status_code == 422

    body = response.json()

    assert body["status"] == "error"
    assert body["message"] == "Validation error"

    assert any(
        error.get("loc") == ["body", field]
        for error in body["detail"]
    )

def test_profile_rejects_duplicate_username(
    client: TestClient,
) -> None:
    existing_user = make_user(
        suffix="username_owner",
    )
    register_user(
        client,
        existing_user,
    )

    current_user = register_and_login(
        client,
        suffix="username_changer",
    )

    response = client.patch(
        "/profiles/me",
        json={
            "username": existing_user.username,
        },
    )

    assert_error(
        response,
        status_code=409,
        detail="USERNAME_TAKEN",
        message="That username is already in use.",
    )

    reread = assert_success(
        client.get("/profiles/me")
    )["data"]

    assert reread["username"] == current_user.username

def test_username_change_enforces_thirty_day_cooldown(
    client: TestClient,
) -> None:
    register_and_login(
        client,
        suffix="username_cooldown",
    )

    first = assert_success(
        client.patch(
            "/profiles/me",
            json={
                "username": "first_updated_username",
            },
        )
    )

    assert (
        first["data"]["username"]
        == "first_updated_username"
    )
    assert (
        first["data"]["username_changed_at"]
        is not None
    )

    second_response = client.patch(
        "/profiles/me",
        json={
            "username": "second_updated_username",
        },
    )

    assert second_response.status_code == 409

    second_body = second_response.json()

    assert second_body["status"] == "error"
    assert (second_body["detail"] == "USERNAME_CHANGE_COOLDOWN")
    assert second_body["message"] == ("Username can only be changed once every 30 days.")
    assert ("next_change_at" in second_body["data"]["detail"])

    reread = assert_success(
        client.get("/profiles/me")
    )["data"]

    assert reread["username"] == (
        "first_updated_username"
    )

def test_displayname_can_change_during_username_cooldown(
    client: TestClient,
) -> None:
    register_and_login(
        client,
        suffix="display_during_cooldown",
    )

    assert_success(
        client.patch(
            "/profiles/me",
            json={
                "username": "cooldown_username",
            },
        )
    )

    display_update = assert_success(
        client.patch(
            "/profiles/me",
            json={
                "displayname": "New Display Name",
            },
        )
    )

    assert (
        display_update["data"]["displayname"]
        == "New Display Name"
    )
    assert (
        display_update["data"]["username"]
        == "cooldown_username"
    )