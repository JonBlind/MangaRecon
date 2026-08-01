from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from backend.db.models.base import Base


class DataProvider(Base):
    """
    External metadata provider used during catalog ingestion.

    Provider-specific identifiers are stored in external-source mapping
    tables rather than directly on Manga or Creator.
    """

    __tablename__ = "data_provider"

    provider_id = Column(Integer, primary_key=True)
    provider_key = Column(String(50), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    attribution_url = Column(String, nullable=False)

    manga_sources = relationship("MangaExternalSource", back_populates="provider", cascade="all, delete-orphan", passive_deletes=True)
    creator_sources = relationship("CreatorExternalSource", back_populates="provider", cascade="all, delete-orphan", passive_deletes=True)
