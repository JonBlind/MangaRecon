import uuid
from sqlalchemy import Column, Date, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_genre, manga_demographic, manga_tag

class Manga(Base):
    '''
    Manga master record with core metadata and relationships.

    Constraints & Notes:
        - `title` is unique.
        - A manga may have zero, one, or multiple credited creators.
        - Creator roles are stored through `MangaCreator`.
        - `external_average_rating` may contain imported/aggregated scores.
        - `average_rating` may reflect internal/user ratings (if computed).

    Relationships:
        - `creator_links` credits creators through `manga_creator`.
        - `ratings` contains personal ratings from users.
        - `genres` contains assigned genres.
        - `tags` contains assigned tags.
        - `demographics` contains intended audiences.
        - `manga_collection_links` connects manga to collections.
    '''
    __tablename__ = "manga"

    manga_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, unique=True)

    description = Column(Text)
    published_date = Column(Date)

    external_average_rating = Column(Numeric(2, 1))
    average_rating = Column(Numeric(2, 1))
    cover_image_url = Column(String)

    # Many-to-many memberships
    creator_links = relationship("MangaCreator", back_populates="manga", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    ratings = relationship("Rating", back_populates="manga", cascade="all, delete-orphan")
    genres = relationship("Genre", secondary=manga_genre, back_populates="manga")
    tags = relationship("Tag", secondary=manga_tag, back_populates="manga")
    demographics = relationship("Demographic", secondary=manga_demographic, back_populates="manga")
    manga_collection_links = relationship("MangaCollection", back_populates="manga", cascade="all, delete-orphan", lazy="selectin")
    