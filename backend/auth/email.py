"""Account-email creation and delivery through Resend."""

from __future__ import annotations

from email.utils import formataddr
from hashlib import sha256
from html import escape
import logging
from typing import Any
from urllib.parse import urlencode

import httpx2

from backend.auth.config import settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """Raised when an account email cannot be delivered."""


def build_verification_url(token: str) -> str:
    """Build the frontend URL that consumes a FastAPI Users verify token."""
    if not settings.frontend_url:
        raise EmailDeliveryError("FRONTEND_URL is not configured.")

    base_url = settings.frontend_url.rstrip("/")
    return f"{base_url}/verify-email?{urlencode({'token': token})}"


def build_password_reset_url(token: str) -> str:
    """Build the frontend URL that consumes a password-reset token."""
    configured_url = settings.password_reset_url

    if configured_url:
        base_url = configured_url.rstrip("/")
    elif settings.frontend_url:
        base_url = f"{settings.frontend_url.rstrip('/')}/reset-password"
    else:
        raise EmailDeliveryError(
            "PASSWORD_RESET_URL or FRONTEND_URL is not configured."
        )

    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode({'token': token})}"


def build_verification_email(
    *,
    recipient: str,
    verification_url: str,
) -> dict[str, Any]:
    """Create the JSON payload accepted by Resend's send-email API."""
    if not settings.resend_from_email:
        raise EmailDeliveryError("RESEND_FROM_EMAIL is not configured.")

    plain_text = (
        "Welcome to MangaRecon.\n\n"
        "Verify your email address by opening this link:\n"
        f"{verification_url}\n\n"
        "This link expires in 3 days. If you did not create a MangaRecon "
        "account, you can ignore this email."
    )
    safe_url = escape(verification_url, quote=True)
    html = (
        "<!doctype html>"
        "<html><body>"
        "<p>Welcome to MangaRecon.</p>"
        f'<p><a href="{safe_url}">Verify your email address</a></p>'
        "<p>This link expires in 3 days. If you did not create a "
        "MangaRecon account, you can ignore this email.</p>"
        "</body></html>"
    )

    return {
        "from": formataddr(
            (
                settings.resend_from_name,
                str(settings.resend_from_email),
            )
        ),
        "to": [recipient],
        "subject": "Verify your MangaRecon email",
        "text": plain_text,
        "html": html,
    }


def build_password_reset_email(
    *,
    recipient: str,
    reset_url: str,
) -> dict[str, Any]:
    """Create a password-reset payload for Resend's send-email API."""
    if not settings.resend_from_email:
        raise EmailDeliveryError("RESEND_FROM_EMAIL is not configured.")

    lifetime = settings.password_reset_token_lifetime_minutes
    plain_text = (
        "A password reset was requested for your MangaRecon account.\n\n"
        "Choose a new password by opening this link:\n"
        f"{reset_url}\n\n"
        f"This link expires in {lifetime} minutes and can only be used once. "
        "If you did not request a password reset, you can ignore this email."
    )
    safe_url = escape(reset_url, quote=True)
    html = (
        "<!doctype html>"
        "<html><body>"
        "<p>A password reset was requested for your MangaRecon account.</p>"
        f'<p><a href="{safe_url}">Choose a new password</a></p>'
        f"<p>This link expires in {lifetime} minutes and can only be used once. "
        "If you did not request a password reset, you can ignore this email.</p>"
        "</body></html>"
    )

    return {
        "from": formataddr(
            (
                settings.resend_from_name,
                str(settings.resend_from_email),
            )
        ),
        "to": [recipient],
        "subject": "Reset your MangaRecon password",
        "text": plain_text,
        "html": html,
    }


def build_verification_idempotency_key(
    *,
    recipient: str,
    token: str,
) -> str:
    """Build a stable, opaque Resend idempotency key for one verify token."""
    digest = sha256(
        f"{recipient.casefold()}\0{token}".encode("utf-8")
    ).hexdigest()
    return f"mangarecon-verification-{digest}"


def build_password_reset_idempotency_key(
    *,
    recipient: str,
    token: str,
) -> str:
    """Build a stable, opaque Resend key for one password-reset token."""
    digest = sha256(
        f"{recipient.casefold()}\0{token}".encode("utf-8")
    ).hexdigest()
    return f"mangarecon-password-reset-{digest}"


async def _send_resend_email(
    payload: dict[str, Any],
    *,
    idempotency_key: str,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> str:
    """Submit one message to Resend and return its provider email ID."""
    if not settings.resend_api_key:
        raise EmailDeliveryError("RESEND_API_KEY is not configured.")

    api_base_url = settings.resend_api_base_url.strip().rstrip("/")
    if not api_base_url:
        raise EmailDeliveryError("RESEND_API_BASE_URL is not configured.")

    headers = {
        "Accept": "application/json",
        "Authorization": (
            "Bearer "
            + settings.resend_api_key.get_secret_value()
        ),
        "Idempotency-Key": idempotency_key,
        "User-Agent": "MangaRecon/0.1",
    }

    try:
        async with httpx2.AsyncClient(
            timeout=settings.resend_timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post(
                f"{api_base_url}/emails",
                headers=headers,
                json=payload,
            )
    except httpx2.RequestError as exc:
        raise EmailDeliveryError(
            "Could not reach the email provider."
        ) from exc

    if not 200 <= response.status_code < 300:
        logger.error(
            "Resend rejected account email (status=%s, request_id=%s).",
            response.status_code,
            response.headers.get("x-request-id"),
        )
        raise EmailDeliveryError("Account email delivery failed.")

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise EmailDeliveryError(
            "The email provider returned an invalid response."
        ) from exc

    email_id = (
        response_payload.get("id")
        if isinstance(response_payload, dict)
        else None
    )
    if not isinstance(email_id, str) or not email_id.strip():
        raise EmailDeliveryError(
            "The email provider returned an invalid response."
        )

    return email_id


async def send_verification_email(
    *,
    recipient: str,
    token: str,
) -> None:
    """Deliver a verification link in disabled, console, or Resend mode."""
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

    payload = build_verification_email(
        recipient=recipient,
        verification_url=verification_url,
    )
    email_id = await _send_resend_email(
        payload,
        idempotency_key=build_verification_idempotency_key(
            recipient=recipient,
            token=token,
        ),
    )
    logger.info(
        "Verification email accepted by Resend (email_id=%s).",
        email_id,
    )


async def send_password_reset_email(
    *,
    recipient: str,
    token: str,
) -> None:
    """Deliver a reset link in disabled, console, or Resend mode."""
    if settings.email_delivery_mode == "disabled":
        return

    reset_url = build_password_reset_url(token)

    if settings.email_delivery_mode == "console":
        logger.warning(
            "Development password-reset link for %s: %s",
            recipient,
            reset_url,
        )
        return

    payload = build_password_reset_email(
        recipient=recipient,
        reset_url=reset_url,
    )
    email_id = await _send_resend_email(
        payload,
        idempotency_key=build_password_reset_idempotency_key(
            recipient=recipient,
            token=token,
        ),
    )
    logger.info(
        "Password-reset email accepted by Resend (email_id=%s).",
        email_id,
    )
