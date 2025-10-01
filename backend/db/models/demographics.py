from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from backend.db.models.base import Base
from backend.db.models.join_tables import manga_demographic

class Demographic(Base):
    '''
    Demographic master record (e.g., Shonen, Seinen, Josei).

    Relationships:
        - `manga` (M:N via `manga_demographic`) titles tagged with this demographic.
    '''
    __tablename__ = "demographic"

    demographic_id = Column(Integer, primary_key=True)
    demographic_name = Column(String(50), nullable=False, unique=True)

    # Many-to-many with manga
    manga = relationship("Manga", secondary=manga_demographic, back_populates="demographics")