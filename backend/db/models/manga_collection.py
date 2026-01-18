import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, TIMESTAMP, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base

class MangaCollection(Base):
    '''
    Association entity connecting manga to collections.

    Primary Key:
        - Composite PK (`collection_id`, `manga_id`).

    Behavior:
        - Both FKs cascade on delete so links disappear when either parent is removed.
        - `added_at` captures when the manga was added to the collection.

    Relationships:
        - `manga` (M:1) linked title.
        - `collection` (M:1) owning collection.
    '''
    __tablename__ = "manga_collection"

    collection_id = Column(Integer, ForeignKey("collection.collection_id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    manga = relationship("Manga", back_populates="manga_collection_links")
    collection = relationship("Collection", back_populates="manga_collection_links")