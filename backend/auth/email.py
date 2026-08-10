"""Verification-email creation and delivery."""

from __future__ import annotations

import asyncio
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import logging
import smtplib
import ssl
from urllib.parse import urlencode

from backend.auth.config import settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when a verification email cannot be delivered."""


def build_verification_url(token: str) -> str:
    """Build the frontend URL that consumes a FastAPI Users verify token."""
    if not settings.frontend_url:
        raise EmailDeliveryError("FRONTEND_URL is not configured.")

    base_url = settings.frontend_url.rstrip("/")
    return f"{base_url}/verify-email?{urlencode({'token': token})}"


def build_verification_message(
    *,
    recipient: str,
    verification_url: str,
) -> EmailMessage:
    """Create the plain-text and HTML verification message."""
    if not settings.smtp_from_email:
        raise EmailDeliveryError("SMTP_FROM_EMAIL is not configured.")

    message = EmailMessage()
    message["Subject"] = "Verify your MangaRecon email"
    message["From"] = formataddr(
        (
            settings.smtp_from_name,
            str(settings.smtp_from_email),
        )
    )
    message["To"] = recipient
    message.set_content(
        "Welcome to MangaRecon.\n\n"
        "Verify your email address by opening this link:\n"
        f"{verification_url}\n\n"
        "This link expires in 3 days. If you did not create a MangaRecon "
        "account, you can ignore this email."
    )
    safe_url = escape(verification_url, quote=True)
    message.add_alternative(
        "<!doctype html>"
        "<html><body>"
        "<p>Welcome to MangaRecon.</p>"
        f'<p><a href="{safe_url}">Verify your email address</a></p>'
        "<p>This link expires in 3 days. If you did not create a "
        "MangaRecon account, you can ignore this email.</p>"
        "</body></html>",
        subtype="html",
    )
    return message


def _send_smtp_message(message: EmailMessage) -> None:
    if not settings.smtp_host:
        raise EmailDeliveryError("SMTP_HOST is not configured.")

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP

    try:
        with smtp_class(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())

            if settings.smtp_username and settings.smtp_password:
                smtp.login(
                    settings.smtp_username,
                    settings.smtp_password,
                )

            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(
            "Verification email delivery failed."
        ) from exc


async def send_verification_email(
    *,
    recipient: str,
    token: str,
) -> None:
    """Deliver a verification link using the configured development or SMTP mode."""
    if settings.email_delivery_mode == "disabled":
        return

    verification_url = build_verification_url(token)

    if settings.email_delivery_mode == "console":
        logger.warning(
            "Development verification link for %s: %s",
            recipient,
            verification_url,
        )
        return

    message = build_verification_message(
        recipient=recipient,
        verification_url=verification_url,
    )
    await asyncio.to_thread(_send_smtp_message, message)
