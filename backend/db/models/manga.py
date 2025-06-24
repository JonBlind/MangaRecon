import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from base import Base
from join_tables import manga_genre, manga_demographic, manga_tag

class Manga(Base):
    __tablename__ = "manga"

    manga_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False, unique=True)
    author_id = Column(Integer, ForeignKey("author.author_id"), nullable=False)

    description = Column(Text)
    published_date = Column(Date)

    external_average_rating = Column(Numeric(2, 1))
    average_rating = Column(Numeric(2, 1))

    author = relationship("Author", back_populates="manga")
    ratings = relationship("Rating", back_populates="manga", cascade="all, delete-orphan")
    collections = relationship("Collection", secondary="manga_collection", back_populates="manga")
    genres = relationship("Genre", secondary=manga_genre, back_populates="manga")
    tags = relationship("Tag", secondary=manga_tag, back_populates="manga")
    demographics = relationship("Demographic", secondary=manga_demographic, back_populates="manga")