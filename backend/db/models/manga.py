import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_genre, manga_demographic, manga_tag

class Manga(Base):
    '''
    Manga master record with core metadata and relationships.

    Constraints & Notes:
        - `title` is unique.
        - `author_id` FK points to `Author`.
        - `external_average_rating` may contain imported/aggregated scores.
        - `average_rating` may reflect internal/user ratings (if computed).

    Relationships:
        - `author` (M:1) primary author of the title.
        - `ratings` (1:M) personal ratings from users.
        - `collections` (M:N via `manga_collection`) collections containing this title.
        - `genres` (M:N via `manga_genre`) assigned genres.
        - `tags` (M:N via `manga_tag`) assigned tags.
        - `demographics` (M:N via `manga_demographic`) intended audiences.
    '''
    __tablename__ = "manga"

    manga_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, unique=True)
    author_id = Column(Integer, ForeignKey("author.author_id"), nullable=False)

    description = Column(Text)
    published_date = Column(Date)

    external_average_rating = Column(Numeric(2, 1))
    average_rating = Column(Numeric(2, 1))

    # Many-to-many memberships
    author = relationship("Author", back_populates="manga")
    ratings = relationship("Rating", back_populates="manga", cascade="all, delete-orphan")
    collections = relationship("Collection", secondary="manga_collection", back_populates="manga")
    genres = relationship("Genre", secondary=manga_genre, back_populates="manga")
    tags = relationship("Tag", secondary=manga_tag, back_populates="manga")
    demographics = relationship("Demographic", secondary=manga_demographic, back_populates="manga")

    cover_image_url = Column(String)