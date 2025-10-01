'''seed metadata (test phase 1)

Revision ID: fba11c90de88
Revises: 97fa363615bb
Create Date: 2025-08-20 13:15:11.401450

'''
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fba11c90de88'
down_revision: Union[str, Sequence[str], None] = '97fa363615bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMOGRAPHICS = [
    "Shounen",
    "Shoujo",
    "Seinen",
    "Josei"
]

GENRES = [
    "Action",
    "Comedy",
    "Drama",
    "Fantasy",
    "Romance"
]

TAGS = [
    "Magic",
    "Time Travel",
    "Isekai",
    "Reincarnation"
    ]

def _insert_values(connection, table: str, col: str, values: list[str]) -> None:
    '''
    Insert a list of strings into a specified table, column.
    '''
    stmt = sa.text(f'''
                    INSERT INTO {sa.text(table).text} ({sa.text(col).text})
                    VALUES (:name)
                    ON CONFLICT ({sa.text(col).text}) DO NOTHING
                   ''')
    for name in values:
        connection.execute(stmt, {"name": name})

def upgrade() -> None:
    '''Upgrade schema.'''
    connection = op.get_bind()

    _insert_values(connection, "demographic", "demographic_name", DEMOGRAPHICS)

    _insert_values(connection, "genre", "genre_name", GENRES)

    _insert_values(connection, "tag", "tag_name", TAGS)


def downgrade() -> None:
    '''Downgrade schema.'''
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM tag WHERE tag_name = ANY(:names)"),
                 {"names": TAGS})
    
    conn.execute(sa.text("DELETE FROM genre WHERE genre_name = ANY(:names)"),
                 {"names": GENRES})
    
    conn.execute(sa.text("DELETE FROM demographic WHERE demographic_name = ANY(:names)"),
                 {"names": DEMOGRAPHICS})
