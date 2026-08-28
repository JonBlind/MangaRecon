from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from backend.db.runtime_roles import (
    REQUIRED_RUNTIME_ROLES,
    RuntimeRoleCredential,
    missing_runtime_roles,
    provision_runtime_roles,
    runtime_role_credentials,
    validate_migration_database_url,
    validate_runtime_roles,
)
from backend.db import runtime_roles


def test_direct_psycopg_migration_url_is_accepted() -> None:
    validate_migration_database_url(
        "postgresql+psycopg://role:password@ep-example.us-east-2.aws.neon.tech/neondb",
        environment="prod",
    )


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://role:password@localhost/mangarecon",
        "postgresql://role:password@localhost/mangarecon",
    ],
)
def test_migration_url_requires_psycopg_driver(database_url: str) -> None:
    with pytest.raises(RuntimeError, match="postgresql\\+psycopg"):
        validate_migration_database_url(
            database_url,
            environment="dev",
        )


def test_production_migration_url_rejects_neon_pooler() -> None:
    with pytest.raises(RuntimeError, match="direct Neon endpoint"):
        validate_migration_database_url(
            "postgresql+psycopg://role:password@ep-example-pooler.us-east-2.aws.neon.tech/neondb",
            environment="prod",
        )


def test_migration_url_rejects_runtime_role() -> None:
    with pytest.raises(RuntimeError, match="separate migration role"):
        validate_migration_database_url(
            "postgresql+psycopg://UserManager:password@localhost/mangarecon",
            environment="dev",
        )


def test_development_migration_url_does_not_apply_neon_host_rule() -> None:
    validate_migration_database_url(
        "postgresql+psycopg://role:password@ep-example-pooler.us-east-2.aws.neon.tech/neondb",
        environment="dev",
    )


def test_missing_runtime_roles_preserves_required_order() -> None:
    assert missing_runtime_roles(
        {"UserManager", "MangaManager"}
    ) == ("UserReader", "MangaReader")


def test_runtime_role_credentials_come_from_application_urls() -> None:
    credentials = runtime_role_credentials(
        {
            "UserWriterDB": "postgresql+asyncpg://UserManager:user-write@localhost/mangarecon",
            "UserReaderDB": "postgresql+asyncpg://UserReader:user-read@localhost/mangarecon",
            "MangaWriterDB": "postgresql+asyncpg://MangaManager:manga-write@localhost/mangarecon",
            "MangaReaderDB": "postgresql+asyncpg://MangaReader:manga-read@localhost/mangarecon",
        }
    )

    assert tuple(item.role_name for item in credentials) == (
        "UserManager",
        "UserReader",
        "MangaManager",
        "MangaReader",
    )
    assert tuple(item.password for item in credentials) == (
        "user-write",
        "user-read",
        "manga-write",
        "manga-read",
    )
    assert "user-write" not in repr(credentials[0])


def test_runtime_role_url_requires_expected_username() -> None:
    with pytest.raises(RuntimeError, match="UserManager"):
        runtime_role_credentials(
            {
                "UserWriterDB": "postgresql+asyncpg://wrong:password@localhost/mangarecon",
            }
        )


def test_runtime_role_url_requires_asyncpg_driver() -> None:
    with pytest.raises(RuntimeError, match="postgresql\\+asyncpg"):
        runtime_role_credentials(
            {
                "UserWriterDB": "postgresql+psycopg://UserManager:password@localhost/mangarecon",
            }
        )


def test_role_provisioning_creates_and_grants_connect() -> None:
    connection = Mock()
    connection.info.dbname = "mangarecon"
    connection.execute.return_value.fetchone.return_value = (
        False,
        False,
        False,
        False,
        False,
    )
    credential = RuntimeRoleCredential(
        role_name="UserManager",
        password="secret",
    )

    with patch(
        "backend.db.runtime_roles._role_exists",
        return_value=False,
    ):
        provision_runtime_roles(connection, (credential,))

    assert connection.execute.call_count == 3


def test_existing_neon_role_has_privileged_membership_removed() -> None:
    connection = Mock()
    connection.info.dbname = "mangarecon"
    connection.execute.return_value.fetchone.return_value = (
        False,
        False,
        False,
        False,
        False,
    )
    credential = RuntimeRoleCredential(
        role_name="UserManager",
        password="secret",
    )

    with (
        patch(
            "backend.db.runtime_roles._role_exists",
            return_value=True,
        ),
        patch(
            "backend.db.runtime_roles._has_neon_superuser_membership",
            return_value=True,
        ),
    ):
        provision_runtime_roles(connection, (credential,))

    assert connection.execute.call_count == 4


def test_runtime_role_attribute_validation_accepts_unprivileged_role() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (
        False,
        False,
        False,
        False,
        False,
    )

    runtime_roles._validate_runtime_role_attributes(
        connection,
        "UserManager",
    )


def test_runtime_role_attribute_validation_rejects_privileged_role() -> None:
    connection = Mock()
    connection.execute.return_value.fetchone.return_value = (
        False,
        True,
        False,
        False,
        True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        runtime_roles._validate_runtime_role_attributes(
            connection,
            "UserManager",
        )

    message = str(exc_info.value)
    assert "CREATEDB" in message
    assert "BYPASSRLS" in message


def test_runtime_role_validation_accepts_all_roles() -> None:
    connection = Mock()
    connection.execute.return_value.scalars.return_value = iter(
        REQUIRED_RUNTIME_ROLES
    )

    validate_runtime_roles(connection)

    connection.execute.assert_called_once()


def test_runtime_role_validation_reports_every_missing_role() -> None:
    connection = Mock()
    connection.execute.return_value.scalars.return_value = iter(
        ("UserManager",)
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_roles(connection)

    message = str(exc_info.value)
    assert "UserReader" in message
    assert "MangaManager" in message
    assert "MangaReader" in message
