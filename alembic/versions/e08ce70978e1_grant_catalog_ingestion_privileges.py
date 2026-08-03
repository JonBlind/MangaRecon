"""grant catalog ingestion privileges

Revision ID: e08ce70978e1
Revises: 2eae692cafa4
Create Date: 2026-08-01 22:56:40.067261
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e08ce70978e1"
down_revision: Union[str, Sequence[str], None] = "2eae692cafa4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant runtime roles access to ingestion-managed catalog data."""
    op.execute(
        """
        GRANT SELECT
        ON TABLE
            data_provider,
            manga_external_source,
            creator_external_source,
            manga_alternate_title
        TO "MangaReader"
        """
    )

    op.execute(
        """
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            data_provider,
            manga_external_source,
            creator_external_source,
            manga_alternate_title
        TO "MangaManager"
        """
    )

    op.execute(
        """
        GRANT USAGE, SELECT
        ON SEQUENCE
            author_author_id_seq,
            data_provider_provider_id_seq,
            demographic_demographic_id_seq,
            genre_genre_id_seq,
            manga_manga_id_seq,
            manga_alternate_title_alternate_title_id_seq,
            tag_tag_id_seq
        TO "MangaManager"
        """
    )


def downgrade() -> None:
    """Revoke the catalog-ingestion privileges added by this revision."""
    op.execute(
        """
        REVOKE USAGE, SELECT
        ON SEQUENCE
            author_author_id_seq,
            data_provider_provider_id_seq,
            demographic_demographic_id_seq,
            genre_genre_id_seq,
            manga_manga_id_seq,
            manga_alternate_title_alternate_title_id_seq,
            tag_tag_id_seq
        FROM "MangaManager"
        """
    )

    op.execute(
        """
        REVOKE SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            data_provider,
            manga_external_source,
            creator_external_source,
            manga_alternate_title
        FROM "MangaManager"
        """
    )

    op.execute(
        """
        REVOKE SELECT
        ON TABLE
            data_provider,
            manga_external_source,
            creator_external_source,
            manga_alternate_title
        FROM "MangaReader"
        """
    )