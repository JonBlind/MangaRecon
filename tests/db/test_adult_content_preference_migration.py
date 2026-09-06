from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "alembic"
    / "versions"
    / "f4b2a8c19d6e_add_adult_content_preferences.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "adult_content_preference_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_safe_defaults_and_backfills_restricted_genres() -> None:
    migration = _load_migration()

    with (
        patch.object(migration.op, "add_column") as add_column,
        patch.object(migration.op, "execute") as execute,
    ):
        migration.upgrade()

    assert migration.down_revision == "c6a4e2f91b73"
    assert add_column.call_count == 2

    manga_table, manga_column = add_column.call_args_list[0].args
    user_table, user_column = add_column.call_args_list[1].args

    assert manga_table == "manga"
    assert manga_column.name == "is_adult_content"
    assert manga_column.nullable is False
    assert str(manga_column.server_default.arg) == "false"

    assert user_table == "user"
    assert user_column.name == "show_adult_content"
    assert user_column.nullable is False
    assert str(user_column.server_default.arg) == "false"

    backfill_sql = execute.call_args.args[0].casefold()
    for genre_name in (
        "adult",
        "hentai",
        "lolicon",
        "shotacon",
        "smut",
    ):
        assert f"'{genre_name}'" in backfill_sql

    assert "'mature'" not in backfill_sql
    assert "'yaoi'" not in backfill_sql
    assert "'yuri'" not in backfill_sql


def test_downgrade_removes_both_columns() -> None:
    migration = _load_migration()

    with patch.object(migration.op, "drop_column") as drop_column:
        migration.downgrade()

    assert drop_column.call_args_list[0].args == (
        "user",
        "show_adult_content",
    )
    assert drop_column.call_args_list[1].args == (
        "manga",
        "is_adult_content",
    )
