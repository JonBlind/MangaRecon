from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from backend.db.models.base import Base


class Creator(Base):
    '''
    Master record for a person credited on one or more manga.

    A creator's role is stored on MangaCreator because the same person may be
    a creator on one manga, an artist on another, or both on the same manga.
    '''
    __tablename__ = "creator"

    creator_id = Column(Integer, primary_key=True)
    creator_name = Column(String(255), nullable=False)

    manga_links = relationship("MangaCreator", back_populates="creator", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    external_sources = relationship("CreatorExternalSource", back_populates="creator", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
