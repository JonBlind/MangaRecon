from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from hashlib import sha256
import hmac

from redis.asyncio import Redis

from backend.cache.redis import get_redis_cache
from backend.config.settings import ENV, settings as app_settings


_MINUTE_SECONDS = 60
_FIFTEEN_MINUTES_SECONDS = 15 * _MINUTE_SECONDS
_HOUR_SECONDS = 60 * _MINUTE_SECONDS
_DAY_SECONDS = 24 * _HOUR_SECONDS


def _auth_secret() -> str:
    """Resolve the HMAC secret without importing auth during app bootstrap."""
    from backend.auth.config import settings as auth_settings

    if not auth_settings.auth_secret:
        raise RuntimeError("AUTH_SECRET is required for account rate limiting.")
    return auth_settings.auth_secret


_FIXED_WINDOW_SCRIPT = """
local allowed = 1
local retry_after = 0

for index, key in ipairs(KEYS) do
    local argument_index = ((index - 1) * 2) + 1
    local request_limit = tonumber(ARGV[argument_index])
    local window_seconds = tonumber(ARGV[argument_index + 1])
    local request_count = tonumber(redis.call("GET", key)) or 0
    local ttl = redis.call("TTL", key)

    if request_count > 0 and ttl < 0 then
        redis.call("EXPIRE", key, window_seconds)
        ttl = window_seconds
    end

    if request_count >= request_limit then
        allowed = 0
        if ttl > retry_after then
            retry_after = ttl
        end
    end
end

-- A request blocked by one window must not consume longer-window capacity.
if allowed == 1 then
    for index, key in ipairs(KEYS) do
        local argument_index = ((index - 1) * 2) + 1
        local window_seconds = tonumber(ARGV[argument_index + 1])
        local request_count = redis.call("INCR", key)

        if request_count == 1 then
            redis.call("EXPIRE", key, window_seconds)
        end
    end
end

return {allowed, retry_after}
"""


class AccountRateLimitStorageError(RuntimeError):
    """Raised when abuse-limit state cannot be checked safely."""


@dataclass(frozen=True)
class AccountRateLimitDecision:
    """Result of reserving capacity in every configured limit window."""

    allowed: bool
    retry_after: int | None = None


@dataclass(frozen=True)
class _RateWindow:
    name: str
    limit: int
    seconds: int


class AccountRateLimiter:
    """Apply atomic fixed-window limits without storing raw identities."""

    def __init__(
        self,
        client_provider: Callable[[], Redis] | None = None,
    ) -> None:
        self._client_provider = (
            client_provider
            if client_provider is not None
            else lambda: get_redis_cache().get_client()
        )

    async def check_email_ip(
        self,
        client_ip: str,
    ) -> AccountRateLimitDecision:
        """Reserve one account-email request for a client IP."""
        return await self._check(
            category="email-ip",
            identity=client_ip,
            windows=(
                _RateWindow(
                    "15-minute",
                    app_settings.account_email_ip_15_minute_limit,
                    _FIFTEEN_MINUTES_SECONDS,
                ),
                _RateWindow(
                    "daily",
                    app_settings.account_email_ip_daily_limit,
                    _DAY_SECONDS,
                ),
            ),
        )

    async def check_token_ip(
        self,
        client_ip: str,
    ) -> AccountRateLimitDecision:
        """Reserve one reset/verification token operation for a client IP."""
        return await self._check(
            category="token-ip",
            identity=client_ip,
            windows=(
                _RateWindow(
                    "minute",
                    app_settings.account_token_ip_minute_limit,
                    _MINUTE_SECONDS,
                ),
            ),
        )

    async def check_recipient(
        self,
        recipient: str,
    ) -> AccountRateLimitDecision:
        """Reserve one account email for a normalized recipient address."""
        return await self._check(
            category="recipient",
            identity=recipient,
            windows=(
                _RateWindow(
                    "cooldown",
                    1,
                    app_settings.account_email_recipient_cooldown_seconds,
                ),
                _RateWindow(
                    "hourly",
                    app_settings.account_email_recipient_hourly_limit,
                    _HOUR_SECONDS,
                ),
                _RateWindow(
                    "daily",
                    app_settings.account_email_recipient_daily_limit,
                    _DAY_SECONDS,
                ),
            ),
        )

    async def _check(
        self,
        *,
        category: str,
        identity: str,
        windows: Sequence[_RateWindow],
    ) -> AccountRateLimitDecision:
        if ENV != "prod":
            return AccountRateLimitDecision(allowed=True)

        identity_digest = self._identity_digest(identity)
        keys = [
            (
                "mangarecon:account-rate:v1:"
                f"{category}:{identity_digest}:{window.name}"
            )
            for window in windows
        ]
        arguments = [
            value
            for window in windows
            for value in (window.limit, window.seconds)
        ]

        try:
            result = await self._client_provider().eval(
                _FIXED_WINDOW_SCRIPT,
                len(keys),
                *keys,
                *arguments,
            )
            allowed, retry_after = self._parse_result(result)
        except Exception as exc:
            raise AccountRateLimitStorageError(
                "Account rate-limit storage is unavailable."
            ) from exc

        return AccountRateLimitDecision(
            allowed=allowed,
            retry_after=(
                None
                if allowed
                else max(1, retry_after)
            ),
        )

    @staticmethod
    def _parse_result(result) -> tuple[bool, int]:
        if (
            not isinstance(result, (list, tuple))
            or len(result) != 2
        ):
            raise ValueError("Invalid account rate-limit response.")

        allowed = int(result[0])
        retry_after = int(result[1])
        if allowed not in (0, 1) or retry_after < 0:
            raise ValueError("Invalid account rate-limit response.")

        return bool(allowed), retry_after

    @staticmethod
    def _identity_digest(identity: str) -> str:
        normalized = identity.strip().casefold().encode("utf-8")
        return hmac.new(
            _auth_secret().encode("utf-8"),
            normalized,
            sha256,
        ).hexdigest()


account_rate_limiter = AccountRateLimiter()
