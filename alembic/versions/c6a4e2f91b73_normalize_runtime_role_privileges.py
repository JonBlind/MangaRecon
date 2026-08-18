"""normalize runtime role privileges

Revision ID: c6a4e2f91b73
Revises: b7c2d4e6f8a1
Create Date: 2026-08-15 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c6a4e2f91b73"
down_revision: Union[str, Sequence[str], None] = "b7c2d4e6f8a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


USER_TABLES = (
    '"user"',
    "collection",
    "manga_collection",
    "rating",
)

CATALOG_TABLES = (
    "manga",
    "creator",
    "demographic",
    "genre",
    "tag",
    "manga_genre",
    "manga_tag",
    "manga_demographic",
    "manga_creator",
    "data_provider",
    "manga_external_source",
    "creator_external_source",
    "manga_alternate_title",
)

USER_SEQUENCES = (
    "collection_collection_id_seq",
)

CATALOG_SEQUENCES = (
    "author_author_id_seq",
    "data_provider_provider_id_seq",
    "demographic_demographic_id_seq",
    "genre_genre_id_seq",
    "manga_manga_id_seq",
    "manga_alternate_title_alternate_title_id_seq",
    "tag_tag_id_seq",
)

RUNTIME_ROLES = (
    '"UserReader"',
    '"UserManager"',
    '"MangaReader"',
    '"MangaManager"',
)


def _objects(names: tuple[str, ...]) -> str:
    return ",\n            ".join(names)


def upgrade() -> None:
    """Apply the current runtime-role privilege matrix."""
    op.execute(
        f"""
        REVOKE ALL PRIVILEGES
        ON TABLE
            {_objects(USER_TABLES + CATALOG_TABLES)}
        FROM {_objects(RUNTIME_ROLES)}
        """
    )
    op.execute(
        f"""
        REVOKE ALL PRIVILEGES
        ON SEQUENCE
            {_objects(USER_SEQUENCES + CATALOG_SEQUENCES)}
        FROM {_objects(RUNTIME_ROLES)}
        """
    )
    op.execute(
        """
        REVOKE ALL
        ON FUNCTION public.refresh_manga_average_rating()
        FROM "UserReader", "UserManager", "MangaReader", "MangaManager"
        """
    )
    op.execute(
        """
        REVOKE CREATE ON SCHEMA public
        FROM "UserReader", "UserManager", "MangaReader", "MangaManager"
        """
    )
    op.execute(
        """
        GRANT USAGE ON SCHEMA public
        TO "UserReader", "UserManager", "MangaReader", "MangaManager"
        """
    )

    op.execute(
        f"""
        GRANT SELECT
        ON TABLE
            {_objects(USER_TABLES)}
        TO "UserReader"
        """
    )
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            {_objects(USER_TABLES)}
        TO "UserManager"
        """
    )
    op.execute(
        f"""
        GRANT USAGE, SELECT
        ON SEQUENCE
            {_objects(USER_SEQUENCES)}
        TO "UserManager"
        """
    )

    op.execute(
        f"""
        GRANT SELECT
        ON TABLE
            {_objects(CATALOG_TABLES)}
        TO "MangaReader"
        """
    )
    op.execute(
        f"""
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            {_objects(CATALOG_TABLES)}
        TO "MangaManager"
        """
    )
    op.execute(
        """
        GRANT EXECUTE
        ON FUNCTION public.refresh_manga_average_rating()
        TO "UserManager", "MangaManager"
        """
    )
    op.execute(
        f"""
        GRANT USAGE, SELECT
        ON SEQUENCE
            {_objects(CATALOG_SEQUENCES)}
        TO "MangaManager"
        """
    )


def downgrade() -> None:
    """Remove privileges managed by this revision."""
    op.execute(
        """
        REVOKE EXECUTE
        ON FUNCTION public.refresh_manga_average_rating()
        FROM "UserManager", "MangaManager"
        """
    )
    op.execute(
        f"""
        REVOKE USAGE, SELECT
        ON SEQUENCE
            {_objects(CATALOG_SEQUENCES)}
        FROM "MangaManager"
        """
    )
    op.execute(
        f"""
        REVOKE SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            {_objects(CATALOG_TABLES)}
        FROM "MangaManager"
        """
    )
    op.execute(
        f"""
        REVOKE SELECT
        ON TABLE
            {_objects(CATALOG_TABLES)}
        FROM "MangaReader"
        """
    )

    op.execute(
        f"""
        REVOKE USAGE, SELECT
        ON SEQUENCE
            {_objects(USER_SEQUENCES)}
        FROM "UserManager"
        """
    )
    op.execute(
        f"""
        REVOKE SELECT, INSERT, UPDATE, DELETE
        ON TABLE
            {_objects(USER_TABLES)}
        FROM "UserManager"
        """
    )
    op.execute(
        f"""
        REVOKE SELECT
        ON TABLE
            {_objects(USER_TABLES)}
        FROM "UserReader"
        """
    )

    op.execute(
        """
        REVOKE USAGE ON SCHEMA public
        FROM "UserReader", "UserManager", "MangaReader", "MangaManager"
        """
    )

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
        f"""
        GRANT USAGE, SELECT
        ON SEQUENCE
            {_objects(CATALOG_SEQUENCES)}
        TO "MangaManager"
        """
    )
    op.execute(
        """
        GRANT EXECUTE
        ON FUNCTION public.refresh_manga_average_rating()
        TO "UserManager", "MangaManager"
        """
    )
