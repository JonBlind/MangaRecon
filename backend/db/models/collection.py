import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from base import Base

class Collection(Base):
    '''
    Collection Model Class. Represents the collection table in the db for sqlalchemy ORM. 
    '''
    __tablename__ = "collection"
    __table_args__ = (UniqueConstraint('user_id', 'collection_name', name='unique_user_collection'),)

    collection_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("profile.user_id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(255), nullable=False)
    description = Column(String(255))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="collections")
    manga = relationship("Manga", secondary="manga_collection", back_populates="collections")