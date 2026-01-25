import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

from backend.main import app
from backend.dependencies import get_user_read_db, get_user_write_db, get_async_user_write_session
from backend.auth.dependencies import current_active_verified_user
from backend.db.client_db import ClientReadDatabase, ClientWriteDatabase
import backend.routes.rating_routes as rating_routes
import backend.routes.profile_routes as profile_routes
from tests.db.factories import make_user

class AuthedClient:
    """
    Wraps an httpx.AsyncClient and forces a specific user dependency override
    for each request, restoring the previous override afterward.

    This allows two "clients" (user A + user B) to coexist in the same test,
    even though FastAPI dependency_overrides is global.
    """
    def __init__(self, client: AsyncClient, user):
        self._client = client
        self._user = user

    async def _with_user(self, coro_fn, *args, **kwargs):
        # Save previous overrides (if any)
        prev_main = app.dependency_overrides.get(current_active_verified_user)

        # profile_routes may use a different dependency object (FastAPI-Users)
        profile_dep = getattr(profile_routes, "current_user", None)
        prev_profile = app.dependency_overrides.get(profile_dep) if profile_dep else None

        async def _current_user_override():
            return self._user

        # Override the dependency used by most routes
        app.dependency_overrides[current_active_verified_user] = _current_user_override

        # ALSO override the dependency used specifically by profile_routes (if present)
        if profile_dep is not None:
            app.dependency_overrides[profile_dep] = _current_user_override

        try:
            return await coro_fn(*args, **kwargs)
        finally:
            # restore main dep
            if prev_main is None:
                app.dependency_overrides.pop(current_active_verified_user, None)
            else:
                app.dependency_overrides[current_active_verified_user] = prev_main

            # restore profile dep
            if profile_dep is not None:
                if prev_profile is None:
                    app.dependency_overrides.pop(profile_dep, None)
                else:
                    app.dependency_overrides[profile_dep] = prev_profile

    async def get(self, *args, **kwargs):
        return await self._with_user(self._client.get, *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._with_user(self._client.post, *args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._with_user(self._client.put, *args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._with_user(self._client.delete, *args, **kwargs)

    async def request(self, *args, **kwargs):
        return await self._with_user(self._client.request, *args, **kwargs)
    
    async def patch(self, *args, **kwargs):
        return await self._with_user(self._client.patch, *args, **kwargs)

    def __getattr__(self, name):
        # passthrough for anything else (headers, base_url, etc.)
        return getattr(self._client, name)


@pytest.fixture
async def authed_user(db_session):
    return await make_user(db_session)


@pytest.fixture
async def other_user(db_session):
    return await make_user(db_session)


@pytest.fixture(autouse=True)
async def override_deps(db_session):
    """
    Global per-test overrides that should be shared for all clients.
    IMPORTANT: do NOT override current_active_verified_user here,
    because user switching is handled per request by AuthedClient.
    """
    read_db = ClientReadDatabase(db_session)
    write_db = ClientWriteDatabase(db_session)

    async def _user_read_db_override():
        yield read_db

    async def _user_write_db_override():
        yield write_db

    async def _override_user_write_session():
        # raw session for fastapi-users
        yield db_session

    app.dependency_overrides[get_user_read_db] = _user_read_db_override
    app.dependency_overrides[get_user_write_db] = _user_write_db_override
    app.dependency_overrides[get_async_user_write_session] = _override_user_write_session

    # prevent rating routes from invalidating recommendations during tests
    async def _noop_invalidate(*args, **kwargs):
        return None

    orig_invalidate = rating_routes.invalidate_user_recommendations
    rating_routes.invalidate_user_recommendations = _noop_invalidate

    yield

    rating_routes.invalidate_user_recommendations = orig_invalidate
    app.dependency_overrides.clear()

@pytest.fixture
async def _raw_async_client():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def async_client(_raw_async_client, authed_user):
    # user A client
    return AuthedClient(_raw_async_client, authed_user)


@pytest.fixture
async def async_client_other_user(_raw_async_client, other_user):
    # user B client
    return AuthedClient(_raw_async_client, other_user)
