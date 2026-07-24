"""add username change cooldown

Revision ID: 31e9aff707e4
Revises: ea4216abfad4
Create Date: 2026-07-24 02:39:41.067478
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "31e9aff707e4"
down_revision: Union[str, Sequence[str], None] = "ea4216abfad4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the timestamp of the user's most recent username change."""
    op.add_column(
        "user",
        sa.Column(
            "username_changed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    op.alter_column(
        "user",
        "username",
        existing_type=sa.String(),
        type_=sa.String(length=64),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Remove the username-change timestamp."""
    op.alter_column(
        "user",
        "username",
        existing_type=sa.String(length=64),
        type_=sa.String(),
        existing_nullable=False,
    )

    op.drop_column(
        "user",
        "username_changed_at",
    )