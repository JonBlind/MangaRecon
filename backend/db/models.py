from sqlalchemy import (Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Numeric, UniqueConstraint, func)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base(cls=AsyncAttrs)

class Profile(Base):
    '''
    Profile Model Class. Represents the profile table in the db for sqlalchemy ORM. 
    '''
    __tablename__ = "profile"

    user_id = Column(Integer, primary_key=True)
    username = Column(Text, nullable=False)
    displayname = Column(Text, nullable=False, unique=True)
    email = Column(Text, nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))

    ratings = relationship("Rating", back_populates="user")
    collections = relationship("Collection", back_populates="user")

class Rating(Base):
    '''
    Rating Model Class. Represents the rating table in the db for sqlalchemy ORM. 
    '''
    __tablename__ = "rating"

    user_id = Column(Integer, ForeignKey("profile.user_id", ondelete="CASCADE"), primary_key=True)
    manga_id = Column(Integer, primary_key=True)
    personal_rating = Column(Numeric(3, 1), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Profile", back_populates="ratings")


class Collection(Base):
    '''
    Collection Model Class. Represents the collection table in the db for sqlalchemy ORM. 
    '''
    __tablename__ = "collection"
    __table_args__ = (UniqueConstraint('user_id', 'collection_name', name='unique_user_collection'),)

    collection_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("profile.user_id", ondelete="CASCADE"), nullable=False)
    collection_name = Column(String(255), nullable=False)
    description = Column(String(255))
    is_public = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("Profile", back_populates="collections")