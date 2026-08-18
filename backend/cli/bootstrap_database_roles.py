from __future__ import annotations

import os
import sys

import psycopg
from dotenv import load_dotenv

from backend.db.runtime_roles import (
    provision_runtime_roles,
    runtime_role_credentials,
    validate_migration_database_url,
)


def _load_environment() -> str:
    initial_environment = os.getenv(
        "MANGARECON_ENV",
        "",
    ).lower().strip()

    if initial_environment == "test":
        load_dotenv(".env.test", override=True)
    else:
        load_dotenv(".env", override=False)

    environment = os.getenv(
        "MANGARECON_ENV",
        "prod",
    ).lower().strip()
    if environment not in {"dev", "test", "prod"}:
        raise RuntimeError(
            "MANGARECON_ENV must be one of: dev, test, prod."
        )
    return environment


def _psycopg_connection_url(database_url: str) -> str:
    return database_url.replace(
        "postgresql+psycopg://",
        "postgresql://",
        1,
    )


def main() -> int:
    try:
        environment = _load_environment()
        database_url = os.getenv("DATABASE_URL_SYNC")
        if not database_url:
            raise RuntimeError("DATABASE_URL_SYNC must be set.")

        validate_migration_database_url(
            database_url,
            environment=environment,
        )
        credentials = runtime_role_credentials(os.environ)

        with psycopg.connect(
            _psycopg_connection_url(database_url)
        ) as connection:
            provision_runtime_roles(connection, credentials)
    except (RuntimeError, psycopg.Error) as exc:
        print(
            f"Database role bootstrap failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print("Runtime database roles provisioned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
