from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models.user import User
from backend.db.models.rating import Rating
from backend.db.models.collection import Collection
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClientDatabase:
    def __init__(self, session: AsyncSession):
        """
        Instance of a user-facing client that interfaces with the database.
        Only includes generic functions that alter the database based on USER interactions.
        """
        self.session = session

    # ====================
    # PROFILE
    # ====================

    async def create_profile(self, data: dict) -> User:
        """
        Create a profile with the provided data and return the User object.
        """
        logger.info(f"Creating profile for email: {data.get('email')}")
        try:
            profile = User(**data)
            self.session.add(profile)
            await self.session.commit()
            await self.session.refresh(profile)
            return profile
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating profile: {str(e)}", exc_info=True)
            raise e

    async def get_profile_by_email(self, email: str) -> Optional[User]:
        """
        Fetches a user by email.
        """
        logger.info(f"Fetching profile by email: {email}")
        try:
            stmt = select(User).where(User.email == email)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch user by email {email}: {str(e)}", exc_info=True)
            return None

    async def get_profile_by_identifier(self, identifier: str) -> Optional[User]:
        """
        Fetches a user by either username or email.
        """
        logger.info(f"Fetching profile by identifier: {identifier}")
        try:
            stmt = select(User).where((User.username == identifier) | (User.email == identifier))
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch user by identifier {identifier}: {str(e)}", exc_info=True)
            return None

    # ====================
    # RATINGS
    # ====================

    @staticmethod
    def _normalize_score(score: float) -> float:
        """
        Clamp to [0, 10] and snap to the nearest 0.5 step to match DB constraints.
        """
        if score is None:
            raise ValueError("Score is required.")
        # clamp
        clamped = max(0.0, min(10.0, float(score)))
        # snap to 0.5
        snapped = round(clamped * 2) / 2.0
        return snapped

    async def rate_manga(self, user_id: uuid.UUID, manga_id: int, score: float) -> Rating:
        """
        Create or update a rating for a manga by the given user (UUID).
        """
        try:
            score_norm = self._normalize_score(score)
            existing = await self.session.get(Rating, (user_id, manga_id))
            if existing:
                existing.personal_rating = score_norm
                logger.info(f"Updated rating: user_id={user_id}, manga_id={manga_id}, score={score_norm}")
                rating = existing
            else:
                rating = Rating(user_id=user_id, manga_id=manga_id, personal_rating=score_norm)
                self.session.add(rating)
                logger.info(f"Created new rating: user_id={user_id}, manga_id={manga_id}, score={score_norm}")
            await self.session.commit()
            await self.session.refresh(rating)
            return rating
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error("Error saving rating", exc_info=True)
            raise e

    async def get_user_rating_for_manga(self, user_id: uuid.UUID, manga_id: int) -> Optional[Rating]:
        """
        Fetch a specific rating for a user and manga.
        """
        try:
            stmt = select(Rating).where(Rating.user_id == user_id, Rating.manga_id == manga_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching rating (user {user_id}, manga {manga_id})", exc_info=True)
            return None

    async def get_all_user_ratings(self, user_id: uuid.UUID) -> List[Rating]:
        """
        Fetch all ratings from a given user.
        """
        try:
            stmt = select(Rating).where(Rating.user_id == user_id)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching all ratings for user {user_id}", exc_info=True)
            return []

    # ====================
    # COLLECTIONS
    # ====================

    async def add_manga_to_collection(self, user_id: uuid.UUID, collection_id: int, manga_id: int) -> None:
        """
        Add a manga to a collection, verifying the user owns the collection.
        """
        try:
            result = await self.session.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise ValueError("Collection not found or unauthorized access.")

            exists = await self.session.execute(
                select(MangaCollection).where(
                    MangaCollection.collection_id == collection_id,
                    MangaCollection.manga_id == manga_id
                )
            )
            if exists.scalar_one_or_none():
                logger.info("Manga already exists in collection.")
                return

            link = MangaCollection(collection_id=collection_id, manga_id=manga_id)
            self.session.add(link)
            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error adding manga to collection: {e}", exc_info=True)
            raise e

    async def remove_manga_from_collection(self, user_id: uuid.UUID, collection_id: int, manga_id: int) -> None:
        """
        Remove a manga from a user-owned collection.
        """
        try:
            # Confirm ownership
            result = await self.session.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise ValueError("Collection not found or unauthorized access.")

            # Find the manga link
            stmt = select(MangaCollection).where(
                MangaCollection.collection_id == collection_id,
                MangaCollection.manga_id == manga_id
            )
            link_result = await self.session.execute(stmt)
            link = link_result.scalar_one_or_none()

            if not link:
                raise ValueError("Manga not found in this collection.")

            await self.session.delete(link)
            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error removing manga {manga_id} from collection {collection_id}: {e}", exc_info=True)
            raise e

    async def get_manga_in_collection(self, user_id: uuid.UUID, collection_id: int) -> List[Manga]:
        """
        Retrieve all manga in a user-owned collection.
        """
        try:
            # Confirm ownership
            result = await self.session.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise ValueError("Collection not found or unauthorized access.")

            # Fetch manga
            stmt = (
                select(Manga)
                .join(MangaCollection)
                .where(MangaCollection.collection_id == collection_id)
            )
            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to fetch manga for collection {collection_id}: {e}", exc_info=True)
            raise e

    async def is_manga_in_collection(self, collection_id: int, manga_id: int) -> bool:
        """
        Check if a manga is already linked to a collection.
        """
        try:
            stmt = select(MangaCollection).where(
                MangaCollection.collection_id == collection_id,
                MangaCollection.manga_id == manga_id
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"Failed to check if manga {manga_id} in collection {collection_id}", exc_info=True)
            return False
