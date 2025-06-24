import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from base import Base

class Author(Base):
    __tablename__ = "author"

    author_id = Column(Integer, primary_key=True)
    author_name = Column(String(255), nullable=False)

    manga = relationship("Manga", back_populates="author", cascade="all, delete-orphan")