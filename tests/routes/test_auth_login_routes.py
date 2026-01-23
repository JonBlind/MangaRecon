import pytest
from tests.db.factories import make_user, DEFAULT_USER_PASSWORD


@pytest.mark.asyncio
async def test_login_sets_cookie_and_allows_access(db_session, _raw_async_client):
    # Create a real user in the DB (verified/active)
    user = await make_user(
        db_session,
        email="login_test@example.com",
        is_active=True,
        is_verified=True,
    )

    async with _raw_async_client.__class__(transport=_raw_async_client._transport, base_url="https://test") as client:
        resp = await client.post(
            "/auth/jwt/login",
            data={"username": user.email, "password": DEFAULT_USER_PASSWORD},
        )

        assert resp.status_code in (200, 204), resp.text
        # Should set auth cookie
        assert "set-cookie" in resp.headers
        assert "auth=" in resp.headers["set-cookie"]

        # Now hit a protected endpoint using the same client (cookie jar)
        r2 = await client.get("/collections/")
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "success"


@pytest.mark.asyncio
async def test_login_rejects_bad_password(db_session, _raw_async_client):
    user = await make_user(
        db_session,
        email="login_badpw@example.com",
        is_active=True,
        is_verified=True,
    )
    async with _raw_async_client.__class__(transport=_raw_async_client._transport, base_url="https://test") as client:
        resp = await client.post(
            "/auth/jwt/login",
            data={"username": user.email, "password": "wrong-password"},
        )
        assert resp.status_code in (400, 401), resp.text
        assert resp.json()["status"] == "error"
