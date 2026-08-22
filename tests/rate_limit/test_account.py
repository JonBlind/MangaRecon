from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.rate_limit import account as account_rate_limit
from backend.rate_limit.account import (
    AccountRateLimiter,
    AccountRateLimitStorageError,
)


def make_limiter(result=(1, 0)):
    client = MagicMock()
    client.eval = AsyncMock(return_value=list(result))
    provider = MagicMock(return_value=client)
    return AccountRateLimiter(client_provider=provider), client, provider


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["dev", "test"])
async def test_limiter_is_disabled_outside_production(
    monkeypatch,
    environment,
):
    limiter, client, provider = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", environment)

    decision = await limiter.check_recipient("reader@example.com")

    assert decision.allowed is True
    assert decision.retry_after is None
    provider.assert_not_called()
    client.eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_email_ip_limit_reserves_both_windows_without_raw_ip(
    monkeypatch,
):
    limiter, client, _ = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_email_ip_15_minute_limit",
        5,
    )
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_email_ip_daily_limit",
        20,
    )

    decision = await limiter.check_email_ip("198.51.100.23")

    assert decision.allowed is True
    arguments = client.eval.await_args.args
    assert arguments[1] == 2
    assert arguments[4:] == (5, 900, 20, 86400)
    assert all("198.51.100.23" not in key for key in arguments[2:4])
    assert all(":email-ip:" in key for key in arguments[2:4])


@pytest.mark.asyncio
async def test_recipient_limit_normalizes_and_hides_email_address(
    monkeypatch,
):
    limiter, client, _ = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_email_recipient_cooldown_seconds",
        60,
    )
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_email_recipient_hourly_limit",
        3,
    )
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_email_recipient_daily_limit",
        5,
    )

    await limiter.check_recipient(" Reader@Example.COM ")
    await limiter.check_recipient("reader@example.com")

    first_arguments = client.eval.await_args_list[0].args
    second_arguments = client.eval.await_args_list[1].args
    first_keys = first_arguments[2:5]
    second_keys = second_arguments[2:5]

    assert first_arguments[1] == 3
    assert first_arguments[5:] == (1, 60, 3, 3600, 5, 86400)
    assert first_keys == second_keys
    assert all("reader@example.com" not in key for key in first_keys)
    assert all(":recipient:" in key for key in first_keys)


@pytest.mark.asyncio
async def test_token_limit_uses_one_minute_window(monkeypatch):
    limiter, client, _ = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")
    monkeypatch.setattr(
        account_rate_limit.app_settings,
        "account_token_ip_minute_limit",
        10,
    )

    await limiter.check_token_ip("2001:db8::1")

    arguments = client.eval.await_args.args
    assert arguments[1] == 1
    assert arguments[3:] == (10, 60)
    assert "2001:db8::1" not in arguments[2]
    assert ":token-ip:" in arguments[2]


@pytest.mark.asyncio
async def test_blocked_limit_returns_retry_after(monkeypatch):
    limiter, _, _ = make_limiter(result=(0, 47))
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")

    decision = await limiter.check_token_ip("198.51.100.23")

    assert decision.allowed is False
    assert decision.retry_after == 47


@pytest.mark.asyncio
async def test_zero_retry_after_is_clamped_for_blocked_limit(monkeypatch):
    limiter, _, _ = make_limiter(result=(0, 0))
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")

    decision = await limiter.check_token_ip("198.51.100.23")

    assert decision.allowed is False
    assert decision.retry_after == 1


@pytest.mark.asyncio
async def test_storage_failure_raises_safe_error(monkeypatch):
    limiter, client, _ = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")
    client.eval.side_effect = RuntimeError("Redis unavailable")

    with pytest.raises(
        AccountRateLimitStorageError,
        match="storage is unavailable",
    ):
        await limiter.check_recipient("reader@example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result",
    [None, [], [1], [1, 0, 3], [2, 0], [1, -1], ["bad", 0]],
)
async def test_invalid_storage_response_raises_safe_error(
    monkeypatch,
    result,
):
    limiter, client, _ = make_limiter()
    monkeypatch.setattr(account_rate_limit, "ENV", "prod")
    client.eval.return_value = result

    with pytest.raises(AccountRateLimitStorageError):
        await limiter.check_token_ip("198.51.100.23")


def test_identity_digest_is_keyed_and_normalized(monkeypatch):
    monkeypatch.setattr(
        account_rate_limit,
        "_auth_secret",
        MagicMock(return_value="different-test-secret"),
    )

    first = AccountRateLimiter._identity_digest(" Reader@Example.COM ")
    second = AccountRateLimiter._identity_digest("reader@example.com")

    assert first == second
    assert first != account_rate_limit.sha256(
        b"reader@example.com"
    ).hexdigest()
    assert len(first) == 64
