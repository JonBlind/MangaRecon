import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, Date, TIMESTAMP, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from base import Base

class MangaCollection(Base):
    __tablename__ = "manga_collection"

    collection_id = Column(Integer, ForeignKey("collection.collection_id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True)
    added_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    manga = relationship("Manga", backref="manga_collection_links")
    collection = relationship("Collection", backref="manga_collection_links")