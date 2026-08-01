"""Update manga metadata and creator credits.

Revision ID: 2eae692cafa4
Revises: d8e3f0a6c1b4
Create Date: 2026-07-31 18:32:16.783716
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Revision identifiers, used by Alembic.
revision: str = "2eae692cafa4"
down_revision: Union[str, Sequence[str], None] = "d8e3f0a6c1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "data_provider",
        sa.Column(
            "provider_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "provider_key",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "attribution_url",
            sa.String(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("provider_id"),
        sa.UniqueConstraint("provider_key"),
    )

    op.create_table(
        "creator_external_source",
        sa.Column(
            "creator_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "external_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "source_url",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["creator_id"],
            ["creator.creator_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["data_provider.provider_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "creator_id",
            "provider_id",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "external_id",
            name=(
                "uq_creator_external_source_"
                "provider_external_id"
            ),
        ),
    )

    op.create_table(
        "manga_alternate_title",
        sa.Column(
            "alternate_title_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "manga_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["manga_id"],
            ["manga.manga_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("alternate_title_id"),
        sa.UniqueConstraint(
            "manga_id",
            "title",
            name="uq_manga_alternate_title_manga_title",
        ),
    )

    op.create_table(
        "manga_external_source",
        sa.Column(
            "manga_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "external_id",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "source_url",
            sa.String(),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "source_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "payload_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["manga_id"],
            ["manga.manga_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["data_provider.provider_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "manga_id",
            "provider_id",
        ),
        sa.UniqueConstraint(
            "provider_id",
            "external_id",
            name=(
                "uq_manga_external_source_"
                "provider_external_id"
            ),
        ),
    )

    op.add_column(
        "manga",
        sa.Column(
            "publication_year",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "manga",
        sa.Column(
            "media_type",
            sa.String(length=50),
            nullable=True,
        ),
    )
    op.add_column(
        "manga",
        sa.Column(
            "external_rating_votes",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Preserve the year from every existing publication date.
    op.execute(
        sa.text(
            """
            UPDATE manga
            SET publication_year =
                EXTRACT(YEAR FROM published_date)::integer
            WHERE published_date IS NOT NULL
            """
        )
    )

    op.alter_column(
        "manga",
        "external_average_rating",
        existing_type=sa.Numeric(
            precision=2,
            scale=1,
        ),
        type_=sa.Numeric(
            precision=4,
            scale=2,
        ),
        existing_nullable=True,
    )
    op.alter_column(
        "manga",
        "average_rating",
        existing_type=sa.Numeric(
            precision=2,
            scale=1,
        ),
        type_=sa.Numeric(
            precision=3,
            scale=1,
        ),
        existing_nullable=True,
    )

    # Titles may repeat, but title-based lookups should remain indexed.
    op.drop_constraint(
        op.f("manga_title_key"),
        "manga",
        type_="unique",
    )

    op.drop_column(
        "manga",
        "published_date",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "manga",
        sa.Column(
            "published_date",
            sa.Date(),
            nullable=True,
        ),
    )

    # Only the publication year remains, so January 1 is used.
    op.execute(
        sa.text(
            """
            UPDATE manga
            SET published_date =
                make_date(publication_year, 1, 1)
            WHERE publication_year IS NOT NULL
            """
        )
    )

    op.create_unique_constraint(
        op.f("manga_title_key"),
        "manga",
        ["title"],
        postgresql_nulls_not_distinct=False,
    )

    op.alter_column(
        "manga",
        "average_rating",
        existing_type=sa.Numeric(
            precision=3,
            scale=1,
        ),
        type_=sa.Numeric(
            precision=2,
            scale=1,
        ),
        existing_nullable=True,
    )
    op.alter_column(
        "manga",
        "external_average_rating",
        existing_type=sa.Numeric(
            precision=4,
            scale=2,
        ),
        type_=sa.Numeric(
            precision=2,
            scale=1,
        ),
        existing_nullable=True,
    )

    op.drop_column(
        "manga",
        "external_rating_votes",
    )
    op.drop_column(
        "manga",
        "media_type",
    )
    op.drop_column(
        "manga",
        "publication_year",
    )

    op.drop_table("manga_external_source")
    op.drop_table("manga_alternate_title")
    op.drop_table("creator_external_source")
    op.drop_table("data_provider")