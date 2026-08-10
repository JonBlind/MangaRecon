from unittest.mock import MagicMock

import pytest

from backend.auth import email


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


def test_build_verification_message_contains_safe_link(
    monkeypatch,
):
    monkeypatch.setattr(
        email.settings,
        "smtp_from_email",
        "noreply@mangarecon.example",
    )
    monkeypatch.setattr(
        email.settings,
        "smtp_from_name",
        "MangaRecon",
    )

    message = email.build_verification_message(
        recipient="reader@example.com",
        verification_url=(
            "https://mangarecon.example/verify-email?token=abc"
        ),
    )

    assert message["Subject"] == "Verify your MangaRecon email"
    assert message["From"] == (
        "MangaRecon <noreply@mangarecon.example>"
    )
    assert message["To"] == "reader@example.com"
    assert "token=abc" in message.get_body(
        preferencelist=("plain",)
    ).get_content()
    assert "Verify your email address" in message.get_body(
        preferencelist=("html",)
    ).get_content()


@pytest.mark.asyncio
async def test_disabled_delivery_does_not_build_or_send(
    monkeypatch,
):
    build_url = MagicMock()
    send_smtp = MagicMock()

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
        "_send_smtp_message",
        send_smtp,
    )

    await email.send_verification_email(
        recipient="reader@example.com",
        token="secret-token",
    )

    build_url.assert_not_called()
    send_smtp.assert_not_called()


@pytest.mark.asyncio
async def test_console_delivery_logs_development_link(
    monkeypatch,
):
    log_warning = MagicMock()

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


def test_smtp_sender_uses_starttls_and_credentials(
    monkeypatch,
):
    smtp = MagicMock()
    smtp.__enter__.return_value = smtp
    smtp_constructor = MagicMock(return_value=smtp)

    monkeypatch.setattr(
        email.settings,
        "smtp_host",
        "smtp.example.com",
    )
    monkeypatch.setattr(email.settings, "smtp_port", 587)
    monkeypatch.setattr(email.settings, "smtp_use_ssl", False)
    monkeypatch.setattr(email.settings, "smtp_starttls", True)
    monkeypatch.setattr(
        email.settings,
        "smtp_username",
        "smtp-user",
    )
    monkeypatch.setattr(
        email.settings,
        "smtp_password",
        "smtp-password",
    )
    monkeypatch.setattr(
        email.settings,
        "smtp_timeout_seconds",
        10.0,
    )
    monkeypatch.setattr(email.smtplib, "SMTP", smtp_constructor)

    message = MagicMock()
    email._send_smtp_message(message)

    smtp_constructor.assert_called_once_with(
        "smtp.example.com",
        587,
        timeout=10.0,
    )
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with(
        "smtp-user",
        "smtp-password",
    )
    smtp.send_message.assert_called_once_with(message)
