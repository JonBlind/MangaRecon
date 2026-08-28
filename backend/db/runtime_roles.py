from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from psycopg import Connection as PsycopgConnection, sql
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.exc import ArgumentError


USER_WRITER_ROLE = "UserManager"
USER_READER_ROLE = "UserReader"
MANGA_WRITER_ROLE = "MangaManager"
MANGA_READER_ROLE = "MangaReader"

REQUIRED_RUNTIME_ROLES = (
    USER_WRITER_ROLE,
    USER_READER_ROLE,
    MANGA_WRITER_ROLE,
    MANGA_READER_ROLE,
)

PROHIBITED_RUNTIME_ROLE_ATTRIBUTES = (
    "SUPERUSER",
    "CREATEDB",
    "CREATEROLE",
    "REPLICATION",
    "BYPASSRLS",
)

RUNTIME_ROLE_URLS = (
    ("UserWriterDB", USER_WRITER_ROLE),
    ("UserReaderDB", USER_READER_ROLE),
    ("MangaWriterDB", MANGA_WRITER_ROLE),
    ("MangaReaderDB", MANGA_READER_ROLE),
)


@dataclass(frozen=True)
class RuntimeRoleCredential:
    role_name: str
    password: str = field(repr=False)


def validate_migration_database_url(
    database_url: str,
    *,
    environment: str,
) -> None:
    try:
        url = make_url(database_url)
    except ArgumentError as exc:
        raise RuntimeError(
            "DATABASE_URL_SYNC must be a valid PostgreSQL URL."
        ) from exc

    if url.drivername != "postgresql+psycopg":
        raise RuntimeError(
            "DATABASE_URL_SYNC must use the postgresql+psycopg driver."
        )

    if url.username in REQUIRED_RUNTIME_ROLES:
        raise RuntimeError(
            "DATABASE_URL_SYNC must use a separate migration role."
        )

    hostname = (url.host or "").casefold()
    if environment == "prod" and "-pooler." in hostname:
        raise RuntimeError(
            "DATABASE_URL_SYNC must use the direct Neon endpoint, "
            "not the pooled endpoint."
        )


def missing_runtime_roles(
    existing_roles: Collection[str],
) -> tuple[str, ...]:
    existing = set(existing_roles)
    return tuple(
        role
        for role in REQUIRED_RUNTIME_ROLES
        if role not in existing
    )


def runtime_role_credentials(
    environment: Mapping[str, str],
) -> tuple[RuntimeRoleCredential, ...]:
    credentials = []

    for variable_name, expected_role in RUNTIME_ROLE_URLS:
        database_url = environment.get(variable_name)
        if not database_url:
            raise RuntimeError(f"{variable_name} must be set.")

        try:
            url = make_url(database_url)
        except ArgumentError as exc:
            raise RuntimeError(
                f"{variable_name} must be a valid PostgreSQL URL."
            ) from exc

        if url.drivername != "postgresql+asyncpg":
            raise RuntimeError(
                f"{variable_name} must use the postgresql+asyncpg driver."
            )
        if url.username != expected_role:
            raise RuntimeError(
                f"{variable_name} must use database role {expected_role}."
            )
        if not url.password:
            raise RuntimeError(f"{variable_name} must include a password.")

        credentials.append(
            RuntimeRoleCredential(
                role_name=expected_role,
                password=url.password,
            )
        )

    return tuple(credentials)


def _role_exists(
    connection: PsycopgConnection,
    role_name: str,
) -> bool:
    result = connection.execute(
        "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s",
        (role_name,),
    )
    return result.fetchone() is not None


def _has_neon_superuser_membership(
    connection: PsycopgConnection,
    role_name: str,
) -> bool:
    result = connection.execute(
        """
        SELECT 1
        FROM pg_catalog.pg_auth_members AS membership
        JOIN pg_catalog.pg_roles AS granted_role
            ON granted_role.oid = membership.roleid
        JOIN pg_catalog.pg_roles AS member_role
            ON member_role.oid = membership.member
        WHERE granted_role.rolname = 'neon_superuser'
          AND member_role.rolname = %s
        """,
        (role_name,),
    )
    return result.fetchone() is not None


def _validate_runtime_role_attributes(
    connection: PsycopgConnection,
    role_name: str,
) -> None:
    """Reject runtime roles that retain privileged PostgreSQL attributes."""
    result = connection.execute(
        """
        SELECT
            rolsuper,
            rolcreatedb,
            rolcreaterole,
            rolreplication,
            rolbypassrls
        FROM pg_catalog.pg_roles
        WHERE rolname = %s
        """,
        (role_name,),
    )
    attributes = result.fetchone()
    if attributes is None:
        raise RuntimeError(
            f"Runtime database role {role_name} does not exist."
        )

    prohibited = tuple(
        attribute_name
        for attribute_name, enabled in zip(
            PROHIBITED_RUNTIME_ROLE_ATTRIBUTES,
            attributes,
            strict=True,
        )
        if enabled
    )
    if prohibited:
        raise RuntimeError(
            f"Runtime database role {role_name} retains prohibited "
            "attributes: "
            + ", ".join(prohibited)
            + "."
        )


def provision_runtime_roles(
    connection: PsycopgConnection,
    credentials: Collection[RuntimeRoleCredential],
) -> None:
    for credential in credentials:
        identifier = sql.Identifier(credential.role_name)
        password = sql.Literal(credential.password)

        if _role_exists(connection, credential.role_name):
            if _has_neon_superuser_membership(
                connection,
                credential.role_name,
            ):
                connection.execute(
                    sql.SQL("REVOKE neon_superuser FROM {}").format(
                        identifier
                    )
                )

            statement = sql.SQL(
                """
                ALTER ROLE {} WITH
                    LOGIN PASSWORD {}
                    NOINHERIT
                """
            ).format(identifier, password)
        else:
            statement = sql.SQL(
                """
                CREATE ROLE {} WITH
                    LOGIN PASSWORD {}
                    NOINHERIT
                """
            ).format(identifier, password)

        connection.execute(statement)
        _validate_runtime_role_attributes(
            connection,
            credential.role_name,
        )
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(connection.info.dbname),
                identifier,
            )
        )


def validate_runtime_roles(connection: Connection) -> None:
    statement = text(
        """
        SELECT rolname
        FROM pg_catalog.pg_roles
        WHERE rolname IN :role_names
        """
    ).bindparams(bindparam("role_names", expanding=True))

    existing_roles = connection.execute(
        statement,
        {"role_names": REQUIRED_RUNTIME_ROLES},
    ).scalars()
    missing = missing_runtime_roles(existing_roles)

    if missing:
        raise RuntimeError(
            "Required database roles do not exist: "
            + ", ".join(missing)
            + ". Provision the runtime roles before running Alembic."
        )
