import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from base import Base

class Rating(Base):
    '''
    Rating Model Class. Represents the rating table in the db for sqlalchemy ORM. 
    '''
    __tablename__ = "rating"

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True)
    personal_rating = Column(Numeric(3, 1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Profile", back_populates="ratings")
    manga = relationship("Manga", back_populates="ratings")