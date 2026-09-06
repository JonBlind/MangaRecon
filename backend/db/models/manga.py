import uuid
from sqlalchemy import Boolean, Column, Date, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_genre, manga_demographic, manga_tag

class Manga(Base):
    '''
    Manga master record with core metadata and relationships.

    Constraints & Notes:
        - Titles are not unique because different manga may share a title.
        - A manga may have zero, one, or multiple credited creators.
        - Creator roles are stored through `MangaCreator`.
        - `external_average_rating` contains a score from the authoritative
          external provider.
        - `average_rating` may reflect internal user ratings.
        - `is_adult_content` stores the ingestion-time safety classification.

    Relationships:
        - `creator_links` credits creators through `manga_creator`.
        - `external_sources` identifies records from external providers.
        - `alternate_titles` contains additional known titles.
        - `ratings` contains personal ratings from users.
        - `genres` contains assigned genres.
        - `tags` contains assigned tags.
        - `demographics` contains intended audiences.
        - `manga_collection_links` connects manga to collections.
    '''
    __tablename__ = "manga"

    manga_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, index=True)

    description = Column(Text)
    publication_year = Column(Integer)
    media_type = Column(String(50))

    external_average_rating = Column(Numeric(4, 2))
    external_rating_votes = Column(Integer)
    average_rating = Column(Numeric(3, 1))
    cover_image_url = Column(String)
    is_adult_content = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # Many-to-many memberships
    creator_links = relationship("MangaCreator", back_populates="manga", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    external_sources = relationship("MangaExternalSource", back_populates="manga", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    alternate_titles = relationship("MangaAlternateTitle", back_populates="manga", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    ratings = relationship("Rating", back_populates="manga", cascade="all, delete-orphan")
    genres = relationship("Genre", secondary=manga_genre, back_populates="manga")
    tags = relationship("Tag", secondary=manga_tag, back_populates="manga")
    demographics = relationship("Demographic", secondary=manga_demographic, back_populates="manga")
    manga_collection_links = relationship("MangaCollection", back_populates="manga", cascade="all, delete-orphan", passive_deletes=True, lazy="raise")
