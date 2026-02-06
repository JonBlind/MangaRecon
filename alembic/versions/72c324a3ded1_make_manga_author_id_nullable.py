'''make manga.author_id nullable

Revision ID: 72c324a3ded1
Revises: 1ce1de1f7a05
Create Date: 2026-02-04 17:42:33.914053

'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72c324a3ded1'
down_revision: Union[str, Sequence[str], None] = '1ce1de1f7a05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("manga", "author_id", existing_type=sa.Integer(), nullable=True)

def downgrade() -> None:
    # This will fail if any rows are NULL at downgrade time (expected).
    op.alter_column("manga", "author_id", existing_type=sa.Integer(), nullable=False)