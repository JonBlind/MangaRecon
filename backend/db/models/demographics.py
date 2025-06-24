from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.orm import relationship
from base import Base
from backend.db.models.join_tables import manga_demographic

class Demographic(Base):
    __tablename__ = "demographic"

    demographic_id = Column(Integer, primary_key=True)
    demographic_name = Column(String(50), nullable=False, unique=True)

    # Many-to-many with manga
    manga = relationship("Manga", secondary=manga_demographic, back_populates="demographics")