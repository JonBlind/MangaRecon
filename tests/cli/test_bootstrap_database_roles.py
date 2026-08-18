from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.cli import bootstrap_database_roles
from backend.db.runtime_roles import RuntimeRoleCredential


def test_psycopg_connection_url_removes_sqlalchemy_driver() -> None:
    assert bootstrap_database_roles._psycopg_connection_url(
        "postgresql+psycopg://role:password@localhost/mangarecon"
    ) == "postgresql://role:password@localhost/mangarecon"


def test_main_provisions_roles(capsys, monkeypatch) -> None:
    database_url = (
        "postgresql+psycopg://admin:password@localhost/mangarecon"
    )
    monkeypatch.setenv("DATABASE_URL_SYNC", database_url)
    credentials = (
        RuntimeRoleCredential(
            role_name="UserManager",
            password="runtime-password",
        ),
    )
    connection = MagicMock()
    connection_context = MagicMock()
    connection_context.__enter__.return_value = connection

    with (
        patch.object(
            bootstrap_database_roles,
            "_load_environment",
            return_value="prod",
        ),
        patch.object(
            bootstrap_database_roles,
            "validate_migration_database_url",
        ) as validate_url,
        patch.object(
            bootstrap_database_roles,
            "runtime_role_credentials",
            return_value=credentials,
        ),
        patch.object(
            bootstrap_database_roles.psycopg,
            "connect",
            return_value=connection_context,
        ) as connect,
        patch.object(
            bootstrap_database_roles,
            "provision_runtime_roles",
        ) as provision,
    ):
        result = bootstrap_database_roles.main()

    assert result == 0
    validate_url.assert_called_once_with(
        database_url,
        environment="prod",
    )
    connect.assert_called_once_with(
        "postgresql://admin:password@localhost/mangarecon"
    )
    provision.assert_called_once_with(connection, credentials)
    assert capsys.readouterr().out == (
        "Runtime database roles provisioned.\n"
    )


def test_main_reports_missing_migration_url(capsys, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL_SYNC", raising=False)

    with patch.object(
        bootstrap_database_roles,
        "_load_environment",
        return_value="prod",
    ):
        result = bootstrap_database_roles.main()

    assert result == 1
    assert "DATABASE_URL_SYNC must be set" in capsys.readouterr().err
