"""add adult content preferences

Revision ID: f4b2a8c19d6e
Revises: c6a4e2f91b73
Create Date: 2026-09-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b2a8c19d6e"
down_revision: Union[str, Sequence[str], None] = "c6a4e2f91b73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store catalog classification and each user's visibility preference."""
    op.add_column(
        "manga",
        sa.Column(
            "is_adult_content",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "user",
        sa.Column(
            "show_adult_content",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.execute(
        """
        UPDATE manga AS catalog_manga
        SET is_adult_content = TRUE
        WHERE EXISTS (
            SELECT 1
            FROM manga_genre
            JOIN genre
              ON genre.genre_id = manga_genre.genre_id
            WHERE manga_genre.manga_id = catalog_manga.manga_id
              AND lower(btrim(genre.genre_name)) IN (
                  'adult',
                  'hentai',
                  'lolicon',
                  'shotacon',
                  'smut'
              )
        )
        """
    )


def downgrade() -> None:
    """Remove adult-content classification and preference fields."""
    op.drop_column("user", "show_adult_content")
    op.drop_column("manga", "is_adult_content")
