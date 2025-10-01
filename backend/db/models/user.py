import uuid
from sqlalchemy import Column, String, Boolean, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.db.models.base import Base

class User(Base):
    '''
    Application user with authentication flags and profile fields.

    Fields:
        - `email`, `hashed_password` for auth.
        - `username`, `displayname` for identity.
        - `is_active`, `is_superuser`, `is_verified` for authorization flow.
        - `created_at`, `last_login` timestamps.

    Relationships:
        - `ratings` (1:M) personal ratings; cascade delete on user removal.
        - `collections` (1:M) user-created collections; cascade delete on user removal.
    '''
    __tablename__ = "user"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)

    username = Column(String, unique=True, nullable=False)
    displayname = Column(String(64), nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    is_verified = Column(Boolean, nullable=False, default=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    last_login = Column(TIMESTAMP(timezone=True))

    ratings = relationship("Rating", back_populates="user", cascade="all, delete-orphan")
    collections = relationship("Collection", back_populates="user", cascade="all, delete-orphan")