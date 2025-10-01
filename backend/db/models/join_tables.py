'''
Association tables linking manga to genres, tags, demographics, and authors.

All foreign keys are `ON DELETE CASCADE` so links are removed when a parent row
is deleted.
'''

from sqlalchemy import (Column, Table, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, TIMESTAMP, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base

# M:N link between manga and genres.
manga_genre = Table(
    "manga_genre",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column("genre_id", Integer, ForeignKey("genre.genre_id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

# M:N link between manga and tags.
manga_tag = Table(
    "manga_tag",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column("tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

# M:N link between manga and demographics.
manga_demographic = Table(
    "manga_demographic",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column("demographic_id", Integer, ForeignKey("demographic.demographic_id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

# M:N link between manga and author.
manga_author = Table(
    "manga_author",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column("author_id", Integer, ForeignKey("author.author_id", ondelete="CASCADE"), primary_key=True, nullable=False),
)