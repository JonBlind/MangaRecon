from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx2
from pydantic import SecretStr
import pytest

from backend.auth import email


def make_resend_transport(
    payload: Any,
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
    requests: list[httpx2.Request] | None = None,
) -> httpx2.MockTransport:
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        if requests is not None:
            requests.append(request)

        return httpx2.Response(
            status_code,
            json=payload,
            headers=headers,
        )

    return httpx2.MockTransport(handler)


def test_build_verification_url_uses_frontend_and_encodes_token(
    monkeypatch,
):
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "https://mangarecon.example/",
    )

    result = email.build_verification_url("token+with/slash=")

    assert result == (
        "https://mangarecon.example/verify-email?"
        "token=token%2Bwith%2Fslash%3D"
    )


def test_build_password_reset_url_uses_configured_url_and_encodes_token(
    monkeypatch,
):
    monkeypatch.setattr(
        email.settings,
        "password_reset_url",
        "https://mangarecon.example/account/reset?source=email",
    )

    result = email.build_password_reset_url("token+with/slash=")

    assert result == (
        "https://mangarecon.example/account/reset?source=email&"
        "token=token%2Bwith%2Fslash%3D"
    )


def test_build_password_reset_url_falls_back_to_frontend_url(
    monkeypatch,
):
    monkeypatch.setattr(email.settings, "password_reset_url", None)
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "https://mangarecon.example/",
    )

    result = email.build_password_reset_url("reset-token")

    assert result == (
        "https://mangarecon.example/reset-password?token=reset-token"
    )


def test_build_verification_email_contains_safe_link(
    monkeypatch,
):
    monkeypatch.setattr(
        email.settings,
        "resend_from_email",
        "noreply@mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_from_name",
        "MangaRecon",
    )

    payload = email.build_verification_email(
        recipient="reader@example.com",
        verification_url=(
            "https://mangarecon.example/verify-email?"
            "token=abc&next=<script>"
        ),
    )

    assert payload["subject"] == "Verify your MangaRecon email"
    assert payload["from"] == (
        "MangaRecon <noreply@mangarecon.example>"
    )
    assert payload["to"] == ["reader@example.com"]
    assert "token=abc&next=<script>" in payload["text"]
    assert "Verify your email address" in payload["html"]
    assert "token=abc&amp;next=&lt;script&gt;" in payload["html"]
    assert "<script>" not in payload["html"]


def test_build_password_reset_email_contains_safe_one_time_link(
    monkeypatch,
):
    monkeypatch.setattr(
        email.settings,
        "resend_from_email",
        "noreply@mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_from_name",
        "MangaRecon",
    )
    monkeypatch.setattr(
        email.settings,
        "password_reset_token_lifetime_minutes",
        30,
    )

    payload = email.build_password_reset_email(
        recipient="reader@example.com",
        reset_url=(
            "https://mangarecon.example/reset-password?"
            "token=abc&next=<script>"
        ),
    )

    assert payload["subject"] == "Reset your MangaRecon password"
    assert payload["from"] == (
        "MangaRecon <noreply@mangarecon.example>"
    )
    assert payload["to"] == ["reader@example.com"]
    assert "expires in 30 minutes" in payload["text"]
    assert "only be used once" in payload["text"]
    assert "token=abc&amp;next=&lt;script&gt;" in payload["html"]
    assert "<script>" not in payload["html"]


def test_verification_idempotency_key_is_stable_and_opaque():
    first = email.build_verification_idempotency_key(
        recipient="Reader@Example.com",
        token="sensitive-verification-token",
    )
    same = email.build_verification_idempotency_key(
        recipient="reader@example.com",
        token="sensitive-verification-token",
    )
    different = email.build_verification_idempotency_key(
        recipient="reader@example.com",
        token="another-token",
    )

    assert first == same
    assert first != different
    assert first.startswith("mangarecon-verification-")
    assert "sensitive-verification-token" not in first
    assert len(first) <= 256


def test_password_reset_idempotency_key_is_stable_and_opaque():
    first = email.build_password_reset_idempotency_key(
        recipient="Reader@Example.com",
        token="sensitive-reset-token",
    )
    same = email.build_password_reset_idempotency_key(
        recipient="reader@example.com",
        token="sensitive-reset-token",
    )
    different = email.build_password_reset_idempotency_key(
        recipient="reader@example.com",
        token="another-token",
    )

    assert first == same
    assert first != different
    assert first.startswith("mangarecon-password-reset-")
    assert "sensitive-reset-token" not in first
    assert len(first) <= 256


@pytest.mark.asyncio
async def test_disabled_delivery_does_not_build_or_send(
    monkeypatch,
):
    build_url = MagicMock()
    send_resend = AsyncMock()

    monkeypatch.setattr(
        email.settings,
        "email_delivery_mode",
        "disabled",
    )
    monkeypatch.setattr(
        email,
        "build_verification_url",
        build_url,
    )
    monkeypatch.setattr(
        email,
        "_send_resend_email",
        send_resend,
    )

    await email.send_verification_email(
        recipient="reader@example.com",
        token="secret-token",
    )

    build_url.assert_not_called()
    send_resend.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_password_reset_delivery_does_not_build_or_send(
    monkeypatch,
):
    build_url = MagicMock()
    send_resend = AsyncMock()

    monkeypatch.setattr(
        email.settings,
        "email_delivery_mode",
        "disabled",
    )
    monkeypatch.setattr(email, "build_password_reset_url", build_url)
    monkeypatch.setattr(email, "_send_resend_email", send_resend)

    await email.send_password_reset_email(
        recipient="reader@example.com",
        token="secret-token",
    )

    build_url.assert_not_called()
    send_resend.assert_not_awaited()


@pytest.mark.asyncio
async def test_console_delivery_logs_development_link(
    monkeypatch,
):
    log_warning = MagicMock()
    send_resend = AsyncMock()

    monkeypatch.setattr(
        email.settings,
        "email_delivery_mode",
        "console",
    )
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "http://localhost:5173",
    )
    monkeypatch.setattr(
        email.logger,
        "warning",
        log_warning,
    )
    monkeypatch.setattr(
        email,
        "_send_resend_email",
        send_resend,
    )

    await email.send_verification_email(
        recipient="reader@example.com",
        token="development-token",
    )

    log_warning.assert_called_once_with(
        "Development verification link for %s: %s",
        "reader@example.com",
        (
            "http://localhost:5173/verify-email?"
            "token=development-token"
        ),
    )
    send_resend.assert_not_awaited()


@pytest.mark.asyncio
async def test_console_password_reset_delivery_logs_development_link(
    monkeypatch,
):
    log_warning = MagicMock()
    send_resend = AsyncMock()

    monkeypatch.setattr(
        email.settings,
        "email_delivery_mode",
        "console",
    )
    monkeypatch.setattr(email.settings, "password_reset_url", None)
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "http://localhost:5173",
    )
    monkeypatch.setattr(email.logger, "warning", log_warning)
    monkeypatch.setattr(email, "_send_resend_email", send_resend)

    await email.send_password_reset_email(
        recipient="reader@example.com",
        token="development-token",
    )

    log_warning.assert_called_once_with(
        "Development password-reset link for %s: %s",
        "reader@example.com",
        (
            "http://localhost:5173/reset-password?"
            "token=development-token"
        ),
    )
    send_resend.assert_not_awaited()


@pytest.mark.asyncio
async def test_resend_delivery_builds_and_dispatches_payload(
    monkeypatch,
):
    send_resend = AsyncMock(return_value="email_123")
    log_info = MagicMock()

    monkeypatch.setattr(
        email.settings,
        "email_delivery_mode",
        "resend",
    )
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "https://mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_from_email",
        "noreply@mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_from_name",
        "MangaRecon",
    )
    monkeypatch.setattr(
        email,
        "_send_resend_email",
        send_resend,
    )
    monkeypatch.setattr(email.logger, "info", log_info)

    await email.send_verification_email(
        recipient="reader@example.com",
        token="production-token",
    )

    send_resend.assert_awaited_once()
    payload = send_resend.await_args.args[0]
    idempotency_key = send_resend.await_args.kwargs[
        "idempotency_key"
    ]

    assert payload["to"] == ["reader@example.com"]
    assert payload["from"] == (
        "MangaRecon <noreply@mangarecon.example>"
    )
    assert "production-token" in payload["text"]
    assert "production-token" not in idempotency_key
    log_info.assert_called_once_with(
        "Verification email accepted by Resend (email_id=%s).",
        "email_123",
    )


@pytest.mark.asyncio
async def test_resend_password_reset_builds_and_dispatches_payload(
    monkeypatch,
):
    send_resend = AsyncMock(return_value="email_reset_123")
    log_info = MagicMock()

    monkeypatch.setattr(email.settings, "email_delivery_mode", "resend")
    monkeypatch.setattr(email.settings, "password_reset_url", None)
    monkeypatch.setattr(
        email.settings,
        "frontend_url",
        "https://mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_from_email",
        "noreply@mangarecon.example",
    )
    monkeypatch.setattr(email.settings, "resend_from_name", "MangaRecon")
    monkeypatch.setattr(email, "_send_resend_email", send_resend)
    monkeypatch.setattr(email.logger, "info", log_info)

    await email.send_password_reset_email(
        recipient="reader@example.com",
        token="production-reset-token",
    )

    send_resend.assert_awaited_once()
    payload = send_resend.await_args.args[0]
    idempotency_key = send_resend.await_args.kwargs["idempotency_key"]

    assert payload["to"] == ["reader@example.com"]
    assert payload["subject"] == "Reset your MangaRecon password"
    assert "production-reset-token" in payload["text"]
    assert "production-reset-token" not in idempotency_key
    log_info.assert_called_once_with(
        "Password-reset email accepted by Resend (email_id=%s).",
        "email_reset_123",
    )


@pytest.mark.asyncio
async def test_resend_sender_uses_expected_api_request(
    monkeypatch,
):
    requests: list[httpx2.Request] = []
    payload = {
        "from": "MangaRecon <noreply@mangarecon.example>",
        "to": ["reader@example.com"],
        "subject": "Verify your MangaRecon email",
        "text": "plain content",
        "html": "<p>HTML content</p>",
    }

    monkeypatch.setattr(
        email.settings,
        "resend_api_key",
        SecretStr("re_fake_test_key"),
    )
    monkeypatch.setattr(
        email.settings,
        "resend_api_base_url",
        "https://api.resend.test/",
    )
    monkeypatch.setattr(
        email.settings,
        "resend_timeout_seconds",
        7.5,
    )

    result = await email._send_resend_email(
        payload,
        idempotency_key="mangarecon-verification-test",
        transport=make_resend_transport(
            {"id": "email_456"},
            requests=requests,
        ),
    )

    assert result == "email_456"
    assert len(requests) == 1

    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.resend.test/emails"
    assert request.headers["Authorization"] == (
        "Bearer re_fake_test_key"
    )
    assert request.headers["Idempotency-Key"] == (
        "mangarecon-verification-test"
    )
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-Agent"] == "MangaRecon/0.1"
    assert json.loads(request.content) == payload


@pytest.mark.asyncio
async def test_resend_sender_wraps_transport_failure(
    monkeypatch,
):
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        raise httpx2.ConnectError(
            "connection failed",
            request=request,
        )

    monkeypatch.setattr(
        email.settings,
        "resend_api_key",
        SecretStr("re_fake_test_key"),
    )

    with pytest.raises(
        email.EmailDeliveryError,
        match="Could not reach the email provider",
    ) as exc_info:
        await email._send_resend_email(
            {},
            idempotency_key="test-key",
            transport=httpx2.MockTransport(handler),
        )

    assert isinstance(
        exc_info.value.__cause__,
        httpx2.ConnectError,
    )


@pytest.mark.asyncio
async def test_resend_sender_rejects_unsuccessful_status(
    monkeypatch,
):
    log_error = MagicMock()

    monkeypatch.setattr(
        email.settings,
        "resend_api_key",
        SecretStr("re_fake_test_key"),
    )
    monkeypatch.setattr(email.logger, "error", log_error)

    with pytest.raises(
        email.EmailDeliveryError,
        match="Account email delivery failed",
    ):
        await email._send_resend_email(
            {},
            idempotency_key="test-key",
            transport=make_resend_transport(
                {"message": "domain is not verified"},
                status_code=403,
                headers={"x-request-id": "request_789"},
            ),
        )

    log_error.assert_called_once_with(
        "Resend rejected account email (status=%s, request_id=%s).",
        403,
        "request_789",
    )


@pytest.mark.parametrize(
    "response_payload",
    [
        [],
        {},
        {"id": ""},
        {"id": 123},
    ],
)
@pytest.mark.asyncio
async def test_resend_sender_rejects_invalid_success_payload(
    monkeypatch,
    response_payload,
):
    monkeypatch.setattr(
        email.settings,
        "resend_api_key",
        SecretStr("re_fake_test_key"),
    )

    with pytest.raises(
        email.EmailDeliveryError,
        match="invalid response",
    ):
        await email._send_resend_email(
            {},
            idempotency_key="test-key",
            transport=make_resend_transport(
                response_payload,
            ),
        )


@pytest.mark.asyncio
async def test_resend_sender_rejects_invalid_json(
    monkeypatch,
):
    async def handler(
        request: httpx2.Request,
    ) -> httpx2.Response:
        return httpx2.Response(
            200,
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )

    monkeypatch.setattr(
        email.settings,
        "resend_api_key",
        SecretStr("re_fake_test_key"),
    )

    with pytest.raises(
        email.EmailDeliveryError,
        match="invalid response",
    ) as exc_info:
        await email._send_resend_email(
            {},
            idempotency_key="test-key",
            transport=httpx2.MockTransport(handler),
        )

    assert isinstance(exc_info.value.__cause__, ValueError)
