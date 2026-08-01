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


class CreatorExternalSource(Base):
    """
    Maps an internal creator to a provider-specific creator record.
    """

    __tablename__ = "creator_external_source"

    __table_args__ = (UniqueConstraint("provider_id","external_id", name="uq_creator_external_source_provider_external_id"),)

    creator_id = Column(Integer, ForeignKey("creator.creator_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    provider_id = Column(Integer, ForeignKey("data_provider.provider_id", ondelete="CASCADE"), primary_key=True, nullable=False)

    external_id = Column(String(255), nullable=False)
    source_url = Column(String)
    fetched_at = Column(DateTime(timezone=True),nullable=False,server_default=func.now())

    creator = relationship("Creator", back_populates="external_sources")
    provider = relationship("DataProvider", back_populates="creator_sources")
