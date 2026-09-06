from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from alembic.config import Config
from alembic.script import ScriptDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "alembic"
    / "versions"
    / "c6a4e2f91b73_normalize_runtime_role_privileges.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "runtime_role_privilege_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table_names(statement: str) -> set[str]:
    body = statement.split("ON TABLE", 1)[1].split("TO ", 1)[0]
    return {
        line.strip().rstrip(",")
        for line in body.splitlines()
        if line.strip()
    }


def test_adult_content_preference_migration_is_head() -> None:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_current_head() == "f4b2a8c19d6e"


def test_upgrade_grants_each_role_only_its_domain() -> None:
    migration = _load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.upgrade()

    statements = [
        call.args[0]
        for call in execute.call_args_list
    ]
    user_reader_grant = next(
        statement
        for statement in statements
        if 'TO "UserReader"' in statement
        and "ON TABLE" in statement
    )
    user_writer_grant = next(
        statement
        for statement in statements
        if 'TO "UserManager"' in statement
        and "ON TABLE" in statement
    )
    manga_reader_grant = next(
        statement
        for statement in statements
        if 'TO "MangaReader"' in statement
        and "ON TABLE" in statement
    )
    manga_writer_grant = next(
        statement
        for statement in statements
        if 'TO "MangaManager"' in statement
        and "ON TABLE" in statement
    )

    user_tables = set(migration.USER_TABLES)
    catalog_tables = set(migration.CATALOG_TABLES)
    assert _table_names(user_reader_grant) == user_tables
    assert _table_names(user_writer_grant) == user_tables
    assert _table_names(manga_reader_grant) == catalog_tables
    assert _table_names(manga_writer_grant) == catalog_tables

    sql = "\n".join(statements)
    assert "collection_collection_id_seq" in sql
    assert "manga_manga_id_seq" in sql
    assert "REVOKE CREATE ON SCHEMA public" in sql


def test_downgrade_revokes_every_managed_role() -> None:
    migration = _load_migration()

    with patch.object(migration.op, "execute") as execute:
        migration.downgrade()

    sql = "\n".join(call.args[0] for call in execute.call_args_list)
    assert 'FROM "UserReader"' in sql
    assert 'FROM "UserManager"' in sql
    assert 'FROM "MangaReader"' in sql
    assert 'FROM "MangaManager"' in sql
