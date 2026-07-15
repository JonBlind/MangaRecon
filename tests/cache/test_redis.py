from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import json
import uuid

import pytest

from backend.cache import redis as redis_module
from backend.cache.redis import RedisCache


@pytest.fixture
def redis_client():
    client = MagicMock()

    client.set = AsyncMock()
    client.get = AsyncMock()
    client.delete = AsyncMock()
    client.close = AsyncMock()

    return client


def attach_client(cache: RedisCache, client):
    cache._client = client
    return cache


def test_get_client_creates_redis_client_from_environment(
    monkeypatch,
):
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_DB", "4")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")

    created_client = MagicMock()
    redis_constructor = MagicMock(
        return_value=created_client
    )

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache()

    result = cache._get_client()

    assert result is created_client

    redis_constructor.assert_called_once_with(
        host="redis.internal",
        port=6380,
        db=4,
        password="secret",
        decode_responses=True,
    )


def test_get_client_uses_default_environment_values(
    monkeypatch,
):
    monkeypatch.delenv("REDIS_HOST", raising=False)
    monkeypatch.delenv("REDIS_PORT", raising=False)
    monkeypatch.delenv("REDIS_DB", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)

    created_client = MagicMock()
    redis_constructor = MagicMock(
        return_value=created_client
    )

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache()

    result = cache._get_client()

    assert result is created_client

    redis_constructor.assert_called_once_with(
        host="localhost",
        port=6379,
        db=0,
        password=None,
        decode_responses=True,
    )


def test_get_client_prefers_constructor_values_over_environment(
    monkeypatch,
):
    monkeypatch.setenv("REDIS_HOST", "environment-host")
    monkeypatch.setenv("REDIS_PORT", "9999")
    monkeypatch.setenv("REDIS_DB", "8")
    monkeypatch.setenv("REDIS_PASSWORD", "environment-password")

    created_client = MagicMock()
    redis_constructor = MagicMock(
        return_value=created_client
    )

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache(
        host="configured-host",
        port=6381,
        db=2,
        password="configured-password",
    )

    result = cache._get_client()

    assert result is created_client

    redis_constructor.assert_called_once_with(
        host="configured-host",
        port=6381,
        db=2,
        password="configured-password",
        decode_responses=True,
    )


def test_get_client_returns_existing_client_without_creating_another(
    monkeypatch,
    redis_client,
):
    redis_constructor = MagicMock()

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache()
    cache._client = redis_client

    first_result = cache._get_client()
    second_result = cache._get_client()

    assert first_result is redis_client
    assert second_result is redis_client
    redis_constructor.assert_not_called()


def test_resolve_ttl_prefers_method_override():
    cache = RedisCache(
        ttl_default=600,
    )

    result = cache._resolve_ttl(30)

    assert result == 30


def test_resolve_ttl_uses_instance_default_when_override_missing():
    cache = RedisCache(
        ttl_default=600,
    )

    result = cache._resolve_ttl(None)

    assert result == 600


def test_resolve_ttl_uses_environment_when_no_other_ttl(
    monkeypatch,
):
    monkeypatch.setenv(
        "CACHE_TTL_SECONDS",
        "900",
    )

    cache = RedisCache()

    result = cache._resolve_ttl(None)

    assert result == 900


def test_resolve_ttl_returns_none_when_no_ttl_is_configured(
    monkeypatch,
):
    monkeypatch.delenv(
        "CACHE_TTL_SECONDS",
        raising=False,
    )

    cache = RedisCache()

    result = cache._resolve_ttl(None)

    assert result is None


def test_resolve_ttl_preserves_zero_override():
    cache = RedisCache(
        ttl_default=600,
    )

    result = cache._resolve_ttl(0)

    assert result == 0


@pytest.mark.asyncio
async def test_set_serializes_value_and_uses_explicit_ttl(
    redis_client,
):
    cache = attach_client(
        RedisCache(ttl_default=600),
        redis_client,
    )

    value = {
        "manga_id": 10,
        "title": "Berserk",
        "genres": ["Action", "Fantasy"],
    }

    await cache.set(
        "recommendations:user:collection",
        value,
        ttl=30,
    )

    redis_client.set.assert_awaited_once_with(
        "recommendations:user:collection",
        json.dumps(value),
        ex=30,
    )


@pytest.mark.asyncio
async def test_set_uses_default_ttl_when_override_is_missing(
    redis_client,
):
    cache = attach_client(
        RedisCache(ttl_default=120),
        redis_client,
    )

    await cache.set(
        "key",
        {"value": 1},
    )

    redis_client.set.assert_awaited_once_with(
        "key",
        '{"value": 1}',
        ex=120,
    )


@pytest.mark.asyncio
async def test_set_allows_no_ttl(
    monkeypatch,
    redis_client,
):
    monkeypatch.delenv(
        "CACHE_TTL_SECONDS",
        raising=False,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    await cache.set(
        "key",
        ["one", "two"],
    )

    redis_client.set.assert_awaited_once_with(
        "key",
        '["one", "two"]',
        ex=None,
    )


@pytest.mark.asyncio
async def test_set_serializes_non_json_types_using_string_conversion(
    redis_client,
):
    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    user_id = uuid.uuid4()
    created_at = datetime(
        2026,
        1,
        2,
        3,
        4,
        tzinfo=timezone.utc,
    )

    value = {
        "user_id": user_id,
        "created_at": created_at,
    }

    await cache.set(
        "key",
        value,
        ttl=45,
    )

    expected_payload = json.dumps(
        value,
        default=str,
    )

    redis_client.set.assert_awaited_once_with(
        "key",
        expected_payload,
        ex=45,
    )


@pytest.mark.asyncio
async def test_set_logs_and_suppresses_client_error(
    monkeypatch,
    redis_client,
):
    redis_client.set.side_effect = RuntimeError(
        "Redis unavailable"
    )

    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.set(
        "broken-key",
        {"value": 1},
    )

    assert result is None

    warning.assert_called_once()

    message = warning.call_args.args[0]

    assert "Redis SET error for broken-key" in message
    assert "Redis unavailable" in message
    assert warning.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_set_logs_and_suppresses_serialization_error(
    monkeypatch,
    redis_client,
):
    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    circular_value = {}
    circular_value["self"] = circular_value

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.set(
        "circular",
        circular_value,
    )

    assert result is None
    redis_client.set.assert_not_awaited()
    warning.assert_called_once()

    assert (
        "Redis SET error for circular"
        in warning.call_args.args[0]
    )


@pytest.mark.asyncio
async def test_get_returns_decoded_json_value(
    redis_client,
):
    redis_client.get.return_value = (
        '{"manga_id": 25, "title": "Monster"}'
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.get("manga:25")

    assert result == {
        "manga_id": 25,
        "title": "Monster",
    }

    redis_client.get.assert_awaited_once_with(
        "manga:25"
    )


@pytest.mark.asyncio
async def test_get_returns_none_for_cache_miss(
    redis_client,
):
    redis_client.get.return_value = None

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.get("missing")

    assert result is None
    redis_client.get.assert_awaited_once_with(
        "missing"
    )


@pytest.mark.asyncio
async def test_get_logs_and_returns_none_for_invalid_json(
    monkeypatch,
    redis_client,
):
    redis_client.get.return_value = "not-json"

    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.get("invalid")

    assert result is None
    warning.assert_called_once()

    message = warning.call_args.args[0]

    assert "Redis GET error for invalid" in message
    assert warning.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_get_logs_and_returns_none_for_client_error(
    monkeypatch,
    redis_client,
):
    redis_client.get.side_effect = RuntimeError(
        "connection lost"
    )

    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.get("key")

    assert result is None
    warning.assert_called_once()

    message = warning.call_args.args[0]

    assert "Redis GET error for key" in message
    assert "connection lost" in message


@pytest.mark.asyncio
async def test_delete_removes_single_key(
    redis_client,
):
    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.delete("key")

    assert result is None
    redis_client.delete.assert_awaited_once_with(
        "key"
    )


@pytest.mark.asyncio
async def test_delete_logs_and_suppresses_error(
    monkeypatch,
    redis_client,
):
    redis_client.delete.side_effect = RuntimeError(
        "delete failed"
    )

    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.delete("key")

    assert result is None
    warning.assert_called_once()

    message = warning.call_args.args[0]

    assert "Redis DELETE error for key" in message
    assert "delete failed" in message
    assert warning.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_delete_multiple_deletes_all_keys_in_one_call(
    redis_client,
):
    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.delete_multiple(
        "key:1",
        "key:2",
        "key:3",
    )

    assert result is None

    redis_client.delete.assert_awaited_once_with(
        "key:1",
        "key:2",
        "key:3",
    )


@pytest.mark.asyncio
async def test_delete_multiple_returns_without_creating_client_when_no_keys(
    monkeypatch,
):
    redis_constructor = MagicMock()

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache()

    result = await cache.delete_multiple()

    assert result is None
    redis_constructor.assert_not_called()


@pytest.mark.asyncio
async def test_delete_multiple_logs_and_suppresses_error(
    monkeypatch,
    redis_client,
):
    redis_client.delete.side_effect = RuntimeError(
        "bulk delete failed"
    )

    warning = MagicMock()

    monkeypatch.setattr(
        redis_module.logger,
        "warning",
        warning,
    )

    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.delete_multiple(
        "key:1",
        "key:2",
        "key:3",
        "key:4",
    )

    assert result is None
    warning.assert_called_once()

    message = warning.call_args.args[0]

    assert "Redis DELETE_MULTIPLE error" in message
    assert "key:1" in message
    assert "key:2" in message
    assert "key:3" in message
    assert "key:4" not in message
    assert "bulk delete failed" in message
    assert warning.call_args.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_close_closes_existing_client_and_clears_reference(
    redis_client,
):
    cache = attach_client(
        RedisCache(),
        redis_client,
    )

    result = await cache.close()

    assert result is None
    redis_client.close.assert_awaited_once()
    assert cache._client is None


@pytest.mark.asyncio
async def test_close_does_nothing_when_client_was_never_created(
    monkeypatch,
):
    redis_constructor = MagicMock()

    monkeypatch.setattr(
        redis_module,
        "Redis",
        redis_constructor,
    )

    cache = RedisCache()

    result = await cache.close()

    assert result is None
    assert cache._client is None
    redis_constructor.assert_not_called()


def test_get_redis_cache_creates_and_reuses_shared_instance(
    monkeypatch,
):
    monkeypatch.setattr(
        redis_module,
        "_redis_cache",
        None,
    )

    first = redis_module.get_redis_cache()
    second = redis_module.get_redis_cache()

    assert isinstance(first, RedisCache)
    assert second is first


def test_get_redis_cache_returns_existing_shared_instance(
    monkeypatch,
):
    existing_cache = MagicMock()

    monkeypatch.setattr(
        redis_module,
        "_redis_cache",
        existing_cache,
    )

    result = redis_module.get_redis_cache()

    assert result is existing_cache