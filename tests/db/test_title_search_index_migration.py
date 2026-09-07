from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "alembic"
    / "versions"
    / "8b24f0c7d1a9_add_trigram_title_search_indexes.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "title_search_index_migration",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_creates_trigram_indexes_without_blocking_writes() -> None:
    migration = _load_migration()

    with (
        patch.object(migration.op, "execute") as execute,
        patch.object(migration.op, "get_context") as get_context,
        patch.object(migration.op, "create_index") as create_index,
    ):
        migration.upgrade()

    assert migration.down_revision == "f4b2a8c19d6e"
    execute.assert_called_once_with("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    get_context.return_value.autocommit_block.assert_called_once_with()

    assert create_index.call_count == 2
    create_index.assert_any_call(
        "ix_manga_title_trgm",
        "manga",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
        postgresql_concurrently=True,
    )
    create_index.assert_any_call(
        "ix_manga_alternate_title_title_trgm",
        "manga_alternate_title",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
        postgresql_concurrently=True,
    )


def test_downgrade_drops_indexes_concurrently_and_preserves_extension() -> None:
    migration = _load_migration()

    with (
        patch.object(migration.op, "execute") as execute,
        patch.object(migration.op, "get_context") as get_context,
        patch.object(migration.op, "drop_index") as drop_index,
    ):
        migration.downgrade()

    execute.assert_not_called()
    get_context.return_value.autocommit_block.assert_called_once_with()
    assert drop_index.call_args_list[0].kwargs == {
        "table_name": "manga_alternate_title",
        "postgresql_concurrently": True,
    }
    assert drop_index.call_args_list[0].args == (
        "ix_manga_alternate_title_title_trgm",
    )
    assert drop_index.call_args_list[1].kwargs == {
        "table_name": "manga",
        "postgresql_concurrently": True,
    }
    assert drop_index.call_args_list[1].args == ("ix_manga_title_trgm",)
