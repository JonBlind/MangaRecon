from sqlalchemy import (Column, Table, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, TIMESTAMP, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from base import Base

manga_genre = Table(
    "manga_genre",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE")),
    Column("genre_id", Integer, ForeignKey("genre.genre_id", ondelete="CASCADE")),
)

manga_tag = Table(
    "manga_tag",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("tag.tag_id", ondelete="CASCADE")),
)

manga_demographic = Table(
    "manga_demographic",
    Base.metadata,
    Column("manga_id", Integer, ForeignKey("manga.manga_id", ondelete="CASCADE")),
    Column("demographic_id", Integer, ForeignKey("demographic.demographic_id", ondelete="CASCADE")),
)