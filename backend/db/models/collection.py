import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base

class Collection(Base):
    '''
    User-owned collection of manga.

    Invariants:
        - (`user_id`, `collection_name`) is unique (see `__table_args__`).
        - Deleting a user cascades to their collections (FK on `user_id`).
    Relationships:
        - `user` (M:1) owner of the collection.
        - `manga` (M:N via `manga_collection`) titles contained in this collection.
    '''
    __tablename__ = "collection"

    # Ensure each user cannot have two collections with the same name.
    __table_args__ = (UniqueConstraint('user_id', 'collection_name', name='unique_user_collection'),)

    collection_id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(255), nullable=False)
    description = Column(String(255))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Many-to-many relationships 
    user = relationship("User", back_populates="collections")
    manga = relationship("Manga", secondary="manga_collection", back_populates="collections", overlaps="manga,collection")
    manga_collection_links = relationship("MangaCollection", back_populates="collection", overlaps="collections,manga")