from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from backend.db.models.base import Base


class MangaExternalSource(Base):
    """
    Maps an internal manga to a provider-specific catalog record.
    """

    __tablename__ = "manga_external_source"

    __table_args__ = (UniqueConstraint("provider_id", "external_id", name="uq_manga_external_source_provider_external_id"),)

    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    provider_id = Column(Integer, ForeignKey("data_provider.provider_id", ondelete="CASCADE"), primary_key=True, nullable=False)

    external_id = Column(String(255), nullable=False)
    source_url = Column(String, nullable=False)
    fetched_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    source_updated_at = Column(DateTime(timezone=True))
    payload_hash = Column(String(64), nullable=False)

    manga = relationship("Manga", back_populates="external_sources")
    provider = relationship("DataProvider", back_populates="manga_sources")
