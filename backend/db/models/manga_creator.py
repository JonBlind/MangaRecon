from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from backend.db.models.base import Base


class MangaCreator(Base):
    """
    Association entity connecting a manga to a credited creator.

    The composite primary key includes role so the same creator may have
    multiple roles on the same manga.
    """

    __tablename__ = "manga_creator"

    __table_args__ = (
        CheckConstraint(
            "role IN ('author', 'artist')",
            name="ck_manga_creator_role",
        ),
        Index(
            "idx_manga_creator_creator_id",
            "creator_id",
        ),
    )

    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    creator_id = Column(Integer, ForeignKey("creator.creator_id", ondelete="CASCADE"), primary_key=True, nullable=False)
    role = Column(String(32), primary_key=True, nullable=False)

    manga = relationship("Manga", back_populates="creator_links")
    creator = relationship("Creator", back_populates="manga_links")