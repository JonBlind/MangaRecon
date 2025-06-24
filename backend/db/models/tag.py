from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from base import Base
from backend.db.models.join_tables import manga_tag

class Tag(Base):
    __tablename__ = "tag"

    tag_id = Column(Integer, primary_key=True)
    tag_name = Column(String(50), nullable=False, unique=True)

    manga = relationship("Manga", secondary=manga_tag, back_populates="tags")