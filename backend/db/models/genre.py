from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from base import Base
from backend.db.models.join_tables import manga_genre

class Genre(Base):
    __tablename__ = "genre"

    genre_id = Column(Integer, primary_key=True)
    genre_name = Column(String(50), nullable=False, unique=True)

    manga = relationship("Manga", secondary=manga_genre, back_populates="genres")