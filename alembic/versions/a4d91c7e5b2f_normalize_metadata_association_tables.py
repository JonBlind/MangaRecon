"""normalize metadata association tables

Revision ID: a4d91c7e5b2f
Revises: 4596bfe836ef
Create Date: 2026-07-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d91c7e5b2f"
down_revision: Union[str, Sequence[str], None] = "4596bfe836ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ASSOCIATION_TABLES = (
    ("manga_genre", "genre_id", "pk_manga_genre"),
    ("manga_tag", "tag_id", "pk_manga_tag"),
    (
        "manga_demographic",
        "demographic_id",
        "pk_manga_demographic",
    ),
)


def upgrade() -> None:
    """Match the metadata association tables to their ORM definitions."""

    for table_name, related_id_column, primary_key_name in ASSOCIATION_TABLES:
        # The original migration allowed incomplete rows. They cannot
        # represent a valid association and would prevent NOT NULL constraints.
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table_name}
                WHERE manga_id IS NULL
                   OR {related_id_column} IS NULL
                """
            )
        )

        # The original migration also allowed duplicate pairs. Keep one copy
        # of each pair before adding the composite primary key.
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table_name} AS duplicate
                USING {table_name} AS keeper
                WHERE duplicate.ctid > keeper.ctid
                  AND duplicate.manga_id = keeper.manga_id
                  AND duplicate.{related_id_column}
                      = keeper.{related_id_column}
                """
            )
        )

        op.alter_column(
            table_name,
            "manga_id",
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )
        op.alter_column(
            table_name,
            related_id_column,
            existing_type=sa.Integer(),
            existing_nullable=True,
            nullable=False,
        )
        op.create_primary_key(
            primary_key_name,
            table_name,
            ["manga_id", related_id_column],
        )


def downgrade() -> None:
    """Restore the nullable, keyless association-table structure."""

    for table_name, related_id_column, primary_key_name in reversed(
        ASSOCIATION_TABLES
    ):
        op.drop_constraint(
            primary_key_name,
            table_name,
            type_="primary",
        )
        op.alter_column(
            table_name,
            related_id_column,
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )
        op.alter_column(
            table_name,
            "manga_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
            nullable=True,
        )
