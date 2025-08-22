"""initial indexes

Revision ID: 1ce1de1f7a05
Revises: fba11c90de88
Create Date: 2025-08-22 01:39:41.997163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ce1de1f7a05'
down_revision: Union[str, Sequence[str], None] = 'fba11c90de88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_manga_title", "manga", ["title"])

    # Join tables 
    op.create_index("ix_manga_genre_manga_id", "manga_genre", ["manga_id"])
    op.create_index("ix_manga_genre_genre_id", "manga_genre", ["genre_id"])

    op.create_index("ix_manga_tag_manga_id", "manga_tag", ["manga_id"])
    op.create_index("ix_manga_tag_tag_id", "manga_tag", ["tag_id"])

    op.create_index("ix_manga_demographic_manga_id", "manga_demographic", ["manga_id"])
    op.create_index("ix_manga_demographic_demographic_id", "manga_demographic", ["demographic_id"])

    op.create_index("ix_manga_collection_collection_id", "manga_collection", ["collection_id"])
    op.create_index("ix_manga_collection_manga_id", "manga_collection", ["manga_id"])

    # Ratings lookup
    op.create_index("ix_rating_user_id", "rating", ["user_id"])
    op.create_index("ix_rating_manga_id", "rating", ["manga_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rating_manga_id", table_name="rating")
    op.drop_index("ix_rating_user_id", table_name="rating")

    op.drop_index("ix_manga_collection_manga_id", table_name="manga_collection")
    op.drop_index("ix_manga_collection_collection_id", table_name="manga_collection")

    op.drop_index("ix_manga_demographic_demographic_id", table_name="manga_demographic")
    op.drop_index("ix_manga_demographic_manga_id", table_name="manga_demographic")

    op.drop_index("ix_manga_tag_tag_id", table_name="manga_tag")
    op.drop_index("ix_manga_tag_manga_id", table_name="manga_tag")

    op.drop_index("ix_manga_genre_genre_id", table_name="manga_genre")
    op.drop_index("ix_manga_genre_manga_id", table_name="manga_genre")

    op.drop_index("ix_manga_title", table_name="manga")
