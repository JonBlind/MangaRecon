import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_unauthenticated_requests_are_rejected(_raw_async_client):
    # Profiles
    resp = await _raw_async_client.get("/profiles/me")
    assert resp.status_code == 401
    assert resp.json()["status"] == "error"

    resp = await _raw_async_client.patch("/profiles/me", json={"displayname": "x"})
    assert resp.status_code == 401
    assert resp.json()["status"] == "error"

    # Collections
    resp = await _raw_async_client.get("/collections/")
    assert resp.status_code == 401
    assert resp.json()["status"] == "error"

    # Ratings
    resp = await _raw_async_client.get("/ratings/")
    assert resp.status_code == 401
    assert resp.json()["status"] == "error"

    # Recommendations
    resp = await _raw_async_client.get(f"/recommendations/{uuid4()}")
    assert resp.status_code == 401
    assert resp.json()["status"] == "error"