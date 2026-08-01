from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.db.models.base import Base


class MangaAlternateTitle(Base):
    """
    Alternate title associated with an internal manga record.
    """

    __tablename__ = "manga_alternate_title"

    __table_args__ = (UniqueConstraint("manga_id", "title", name="uq_manga_alternate_title_manga_title"),)

    alternate_title_id = Column(Integer, primary_key=True)
    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    manga = relationship("Manga", back_populates="alternate_titles")
