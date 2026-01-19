import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from backend.main import app
from backend.dependencies import get_user_read_db, get_user_write_db
from backend.auth.dependencies import current_active_verified_user
from tests.db.factories import make_user
import backend.routes.rating_routes as rating_routes


@pytest.fixture
async def async_client():
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def authed_user(db_session):
    return await make_user(db_session)


@pytest.fixture(autouse=True)
async def override_deps(client_db, authed_user):
    async def _user_read_db_override():
        yield client_db

    async def _user_write_db_override():
        yield client_db

    async def _current_user_override():
        return authed_user

    app.dependency_overrides[get_user_read_db] = _user_read_db_override
    app.dependency_overrides[get_user_write_db] = _user_write_db_override
    app.dependency_overrides[current_active_verified_user] = _current_user_override

    async def _noop_invalidate(*args, **kwargs):
        return None

    orig_invalidate = rating_routes.invalidate_user_recommendations
    rating_routes.invalidate_user_recommendations = _noop_invalidate

    yield

    rating_routes.invalidate_user_recommendations = orig_invalidate
    app.dependency_overrides.clear()