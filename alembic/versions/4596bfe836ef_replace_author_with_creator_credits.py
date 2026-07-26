'''replace author with creator credits

Revision ID: 4596bfe836ef
Revises: 31e9aff707e4
Create Date: 2026-07-25 19:38:17.997681

'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4596bfe836ef'
down_revision: Union[str, Sequence[str], None] = '31e9aff707e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace the legacy author structures with creator credits."""

    # Rename the person entity while preserving all existing rows and IDs.
    op.rename_table("author", "creator")

    op.alter_column(
        "creator",
        "author_id",
        new_column_name="creator_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "creator",
        "author_name",
        new_column_name="creator_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    # Create the authoritative creator-credit association.
    op.create_table(
        "manga_creator",
        sa.Column("manga_id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "role IN ('author', 'artist')",
            name="ck_manga_creator_role",
        ),
        sa.ForeignKeyConstraint(
            ["manga_id"],
            ["manga.manga_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "manga_id",
            "creator_id",
            "role",
            name="pk_manga_creator",
        ),
    )

    op.create_index(
        "idx_manga_creator_creator_id",
        "manga_creator",
        ["creator_id"],
    )

    # Preserve relationships already stored in the old join table.
    # Its old structure did not distinguish roles, so they become authors.
    op.execute(
        """
        INSERT INTO manga_creator (manga_id, creator_id, role)
        SELECT DISTINCT
            manga_id,
            author_id,
            'author'
        FROM manga_author
        WHERE manga_id IS NOT NULL
          AND author_id IS NOT NULL
        ON CONFLICT (manga_id, creator_id, role) DO NOTHING
        """
    )

    # Preserve direct manga.author_id relationships that were not present in
    # the old join table.
    op.execute(
        """
        INSERT INTO manga_creator (manga_id, creator_id, role)
        SELECT
            manga_id,
            author_id,
            'author'
        FROM manga
        WHERE author_id IS NOT NULL
        ON CONFLICT (manga_id, creator_id, role) DO NOTHING
        """
    )

    # Data is now safely represented by manga_creator.
    op.drop_table("manga_author")

    op.drop_constraint(
        "manga_author_id_fkey",
        "manga",
        type_="foreignkey",
    )
    op.drop_column("manga", "author_id")


def downgrade() -> None:
    """Restore the legacy author structures."""

    # Restore the optional direct author reference.
    op.add_column(
        "manga",
        sa.Column("author_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "manga_author_id_fkey",
        "manga",
        "creator",
        ["author_id"],
        ["creator_id"],
    )

    # Restore the old role-less association table.
    op.create_table(
        "manga_author",
        sa.Column("manga_id", sa.Integer(), nullable=True),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["manga_id"],
            ["manga.manga_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["creator.creator_id"],
            ondelete="CASCADE",
        ),
    )

    # The legacy table cannot store roles, but it can preserve every distinct
    # manga–creator pairing.
    op.execute(
        """
        INSERT INTO manga_author (manga_id, author_id)
        SELECT DISTINCT
            manga_id,
            creator_id
        FROM manga_creator
        """
    )

    # The direct column can hold only one creator. Prefer an author; when no
    # author exists, select the lowest creator ID deterministically.
    op.execute(
        """
        UPDATE manga
        SET author_id = selected.creator_id
        FROM (
            SELECT
                manga_id,
                COALESCE(
                    MIN(creator_id) FILTER (WHERE role = 'author'),
                    MIN(creator_id)
                ) AS creator_id
            FROM manga_creator
            GROUP BY manga_id
        ) AS selected
        WHERE manga.manga_id = selected.manga_id
        """
    )

    op.drop_table("manga_creator")

    op.alter_column(
        "creator",
        "creator_id",
        new_column_name="author_id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "creator",
        "creator_name",
        new_column_name="author_name",
        existing_type=sa.String(length=255),
        existing_nullable=False,
    )

    op.rename_table("creator", "author")