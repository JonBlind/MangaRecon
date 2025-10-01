from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_tag

class Tag(Base):
    '''
    Tag master record for fine-grained classification (e.g., Time Travel, Found Family).

    Relationships:
        - `manga` (M:N via `manga_tag`) titles associated with this tag.
    '''
    __tablename__ = "tag"

    tag_id = Column(Integer, primary_key=True)
    tag_name = Column(String(50), nullable=False, unique=True)

    manga = relationship("Manga", secondary=manga_tag, back_populates="tags")