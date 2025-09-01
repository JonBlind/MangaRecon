import os
import re
import json
import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")
BASE_URL = "http://testserver"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session")
def app():
    from backend.main import app as fastapi_app
    return fastapi_app

@pytest.fixture
async def client(app):
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
            yield ac



# --- Auth Helpers --- #

EMAIL_RE = re.compile(r"email", re.I)

def _extract_token_from_logs(caplog) -> str | None:
    """
    fastapi-users logs verification/reset tokens in UserManager hooks.
    So this helps parse tokens out.
    """
    token_re = re.compile(r"(verify|verification|reset).*token.*?:\s*([A-Za-z0-9\-\._]+)", re.I)

    # Search newest-first
    for rec in reversed(caplog.records):
        m = token_re.search(rec.getMessage())
        if m:
            return m.group(2)
    return None

async def _register_user(client, email: str, password: str, displayname: str = "Test User"):
    payload = {"email": email, "password": password}
    r = await client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code in (200, 201, 202), r.text

@pytest.fixture
async def auth_headers(client, caplog):
    """
    End-to-end: register -> request verify token -> verify -> login -> return Bearer headers
    """
    email = "tester@example.com"
    password = "BestPassword"

    # Register
    await _register_user(client, email, password)

    # Ask for verification token
    r = await client.post("/auth/request-verify-token", json={"email": email})
    assert r.status_code in (200, 202), r.text

    # Extract token captured in UserManager logs 
    token = _extract_token_from_logs(caplog)
    assert token, "Verification token not found in logs. Adjust regex in tests/conftest.py"

    # Verify account
    r = await client.post("/auth/verify", json={"token": token})
    assert r.status_code in (200, 202), r.text

    # Login to get JWT
    r = await client.post(
        "/auth/jwt/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    access = data.get("access_token") or data.get("access")
    assert access, f"Login response missing access token: {data}"
    return {"Authorization": f"Bearer {access}"}