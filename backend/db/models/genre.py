from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_genre

class Genre(Base):
    '''
    Genre master record (e.g., Action, Romance, Mystery).

    Relationships:
        - `manga` (M:N via `manga_genre`) titles classified under this genre.
    '''
    __tablename__ = "genre"

    genre_id = Column(Integer, primary_key=True)
    genre_name = Column(String(50), nullable=False, unique=True)

    manga = relationship("Manga", secondary=manga_genre, back_populates="genres")