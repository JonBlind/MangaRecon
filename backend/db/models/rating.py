import uuid
from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func, CheckConstraint)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base

class Rating(Base):
    '''
    Personal rating given by a user to a manga.

    Primary Key:
        - Composite PK (`user_id`, `manga_id`).

    Constraints:
        - `personal_rating` is in [0, 10] and restricted to 0.5 increments
          (see `rating_range_check` and `rating_half_step_check`).

    Relationships:
        - `user` (M:1) owner of the rating.
        - `manga` (M:1) rated title. 
    '''
    __tablename__ = "rating"

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(Integer, ForeignKey("manga.manga_id", ondelete="CASCADE"), primary_key=True)
    personal_rating = Column(Numeric(3, 1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint('personal_rating >= 0 AND personal_rating <= 10', name='rating_range_check'),
        CheckConstraint('mod(personal_rating * 2, 1) = 0', name='rating_half_step_check'),
    )

    user = relationship("User", back_populates="ratings")
    manga = relationship("Manga", back_populates="ratings")