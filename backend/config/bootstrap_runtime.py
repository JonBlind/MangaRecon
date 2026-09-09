from __future__ import annotations

import time

_BOOTSTRAP_STARTED_AT = time.perf_counter()

import json
import os
from collections.abc import Mapping

import boto3

from backend.utils.performance import emit_elapsed

SECRET_ID_ENV = "AWS_SECRETS_MANAGER_SECRET_ID"

REQUIRED_SECRET_KEYS = frozenset(
    {
        "AUTH_SECRET",
        "MangaReaderDB",
        "MangaWriterDB",
        "ORIGIN_VERIFY_SECRET_DIGEST",
        "REDIS_URL",
        "RESEND_API_KEY",
        "UserReaderDB",
        "UserWriterDB",
    }
)


def _parse_secret_payload(secret_string: str) -> dict[str, str]:
    """Parse and strictly validate MangaRecon's runtime secret object."""
    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "The runtime secret must be a valid JSON object."
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "The runtime secret must be a JSON object."
        )

    keys = set(payload)
    missing = sorted(REQUIRED_SECRET_KEYS - keys)
    unexpected = sorted(keys - REQUIRED_SECRET_KEYS)

    if missing:
        raise RuntimeError(
            "The runtime secret is missing required keys: "
            + ", ".join(missing)
            + "."
        )

    if unexpected:
        raise RuntimeError(
            "The runtime secret contains unexpected keys: "
            + ", ".join(unexpected)
            + "."
        )

    invalid = sorted(
        key
        for key, value in payload.items()
        if not isinstance(value, str) or not value.strip()
    )
    if invalid:
        raise RuntimeError(
            "The runtime secret contains empty or non-string values for: "
            + ", ".join(invalid)
            + "."
        )

    return payload


def load_runtime_secrets() -> None:
    """Load the configured Secrets Manager JSON object into the environment."""
    secret_id = os.getenv(SECRET_ID_ENV, "").strip()
    if not secret_id:
        return

    try:
        response: Mapping[str, object] = boto3.client(
            "secretsmanager"
        ).get_secret_value(SecretId=secret_id)
    except Exception as exc:
        raise RuntimeError(
            "Unable to load MangaRecon runtime secrets from AWS Secrets Manager."
        ) from exc

    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise RuntimeError(
            "The MangaRecon runtime secret must contain SecretString JSON."
        )

    for key, value in _parse_secret_payload(secret_string).items():
        os.environ[key] = value


def _run_uvicorn() -> None:
    """Start Uvicorn without launching a second Python interpreter."""
    uvicorn_import_started_at = time.perf_counter()
    import uvicorn

    emit_elapsed("uvicorn_import", uvicorn_import_started_at)
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
    )

def main() -> None:
    """Load runtime secrets, then run Uvicorn in this process."""
    secret_load_started_at = time.perf_counter()
    secret_configured = bool(os.getenv(SECRET_ID_ENV, "").strip())

    try:
        load_runtime_secrets()
    except Exception:
        emit_elapsed(
            "runtime_secret_load",
            secret_load_started_at,
            outcome="error",
        )
        raise

    emit_elapsed(
        "runtime_secret_load",
        secret_load_started_at,
        outcome="success" if secret_configured else "skipped",
    )
    emit_elapsed(
        "bootstrap_before_uvicorn",
        _BOOTSTRAP_STARTED_AT,
    )

    _run_uvicorn()


if __name__ == "__main__":
    main()
