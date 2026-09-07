"""add trigram title search indexes

Revision ID: 8b24f0c7d1a9
Revises: f4b2a8c19d6e
Create Date: 2026-09-06 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8b24f0c7d1a9"
down_revision: Union[str, Sequence[str], None] = "f4b2a8c19d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Accelerate case-insensitive substring searches across known titles."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    with op.get_context().autocommit_block():
        op.create_index(
            "ix_manga_title_trgm",
            "manga",
            ["title"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_manga_alternate_title_title_trgm",
            "manga_alternate_title",
            ["title"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Remove title-search indexes while preserving the shared extension."""
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_manga_alternate_title_title_trgm",
            table_name="manga_alternate_title",
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_manga_title_trgm",
            table_name="manga",
            postgresql_concurrently=True,
        )
