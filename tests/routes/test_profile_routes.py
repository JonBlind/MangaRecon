import pytest
from uuid import UUID

@pytest.mark.asyncio
async def test_get_my_profile(async_client, authed_user):

    resp = await async_client.get("/profiles/me")
    assert resp.status_code == 200

    data = resp.json()

    assert data["status"] == "success"
    profile = data["data"]

    assert UUID(profile["id"]) == authed_user.id
    assert profile["email"] == authed_user.email


@pytest.mark.asyncio
async def test_patch_displayname_updates(async_client):
    payload = {"displayname": "New Display Name"}

    resp = await async_client.patch("/profiles/me", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "success"
    profile = data["data"]
    assert profile["displayname"] == "New Display Name"

    # verify data is the same with a second read
    resp2 = await async_client.get("/profiles/me")
    assert resp2.status_code == 200
    profile2 = resp2.json()["data"]
    assert profile2["displayname"] == "New Display Name"

@pytest.mark.asyncio
async def test_change_my_password_success(async_client, authed_user):
    resp = await async_client.post(
        "/profiles/me/change-password",
        json={"current_password": "password", "new_password": "NewPassword123!!"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"

@pytest.mark.asyncio
async def test_change_my_password_rejects_wrong_current(async_client):
    resp = await async_client.post(
        "/profiles/me/change-password",
        json={"current_password": "WRONG", "new_password": "NewPassword123!!"},
    )
    assert resp.status_code == 400
    assert resp.json()["status"] == "error"

@pytest.mark.asyncio
async def test_change_my_password_rejects_invalid_new_password(async_client):
    resp = await async_client.post(
        "/profiles/me/change-password",
        json={"current_password": "password", "new_password": "x"},
    )
    assert resp.status_code in (400, 422)
    assert resp.json()["status"] == "error"