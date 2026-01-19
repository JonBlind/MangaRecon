'''
High-level database helper used by API handlers.

Wraps an async SQLAlchemy `AsyncSession` and exposes safe, user-facing
operations for profiles, ratings, and collections. All mutating methods
handle commit/rollback and log failures with context.
'''


from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from backend.db.models.user import User
from backend.db.models.rating import Rating
from backend.db.models.collection import Collection
from backend.db.models.manga import Manga
from backend.db.models.manga_collection import MangaCollection

logger = logging.getLogger(__name__)


class ClientDatabase:
    '''
    Wraps an async SQLAlchemy `AsyncSession` and exposes safe, user-facing
    operations for profiles, ratings, and collections. All mutating methods
    handle commit/rollback and log failures with context.
    '''
    def __init__(self, session: AsyncSession):
        self.session = session

    # ====================
    # PROFILE
    # ====================

    async def create_profile(self, data: dict) -> User:
        '''
        Create a new `User` row from the provided dict payload and return it.

        Args:
            data (dict): Field/value mapping corresponding to the `User` ORM constructor.

        Returns:
            User: Freshly created user row (post-commit/refresh).

        Raises:
            SQLAlchemyError: On insert/commit errors (session rolled back).
        '''
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
            raise

    async def get_profile_by_email(self, email: str) -> Optional[User]:
        '''
        Fetch a single user by email.

        Args:
            email (str): Email address to match.

        Returns:
            Optional[User]: Matching user if found, otherwise `None`.
        '''
        logger.info(f"Fetching profile by email: {email}")
        try:
            stmt = select(User).where(User.email == email)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch user by email {email}: {str(e)}", exc_info=True)
            return None

    async def get_profile_by_identifier(self, identifier: str) -> Optional[User]:
        '''
        Fetch a single user by username **or** email.

        Args:
            identifier (str): Username or email to match.

        Returns:
            Optional[User]: Matching user if found, otherwise `None`.
        '''
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
        '''
        Clamp and quantize a rating value to DB constraints.

        - Clamps to the inclusive range [0.0, 10.0]
        - Rounds to the nearest 0.5 increment

        Args:
            score (float): Raw score input.

        Returns:
            float: Normalized score suitable for persistence.

        Raises:
            ValueError: If `score` is `None`.
        '''
        if score is None:
            raise ValueError("Score is required.")
        # clamp
        clamped = max(0.0, min(10.0, float(score)))
        # snap to 0.5
        snapped = round(clamped * 2) / 2.0
        return snapped

    async def rate_manga(self, user_id: uuid.UUID, manga_id: int, score: float) -> Rating:
        '''
        Create or update the caller's personal rating for a manga.

        If an existing `(user_id, manga_id)` rating is present, it is updated;
        otherwise a new row is inserted.

        Args:
            user_id (uuid.UUID): Owner of the rating.
            manga_id (int): Target manga identifier.
            score (float): Personal rating value (normalized to [0,10] in 0.5 steps).

        Returns:
            Rating: The upserted rating (post-commit/refresh).

        Raises:
            SQLAlchemyError: On DB write failure (session rolled back).
        '''
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
            raise

    async def get_user_rating_for_manga(self, user_id: uuid.UUID, manga_id: int) -> Optional[Rating]:
        '''
        Retrieve the caller's rating for a specific manga.

        Args:
            user_id (uuid.UUID): Owner of the rating.
            manga_id (int): Target manga identifier.

        Returns:
            Optional[Rating]: Rating if present, otherwise `None`.
        '''
        try:
            stmt = select(Rating).where(Rating.user_id == user_id, Rating.manga_id == manga_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching rating (user {user_id}, manga {manga_id})", exc_info=True)
            return None

    async def get_all_user_ratings(self, user_id: uuid.UUID) -> List[Rating]:
        '''
        Retrieve all ratings authored by the given user.

        Args:
            user_id (uuid.UUID): Owner whose ratings to list.

        Returns:
            List[Rating]: Possibly empty list of ratings. Returns `[]` on errors.
        '''
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
        '''
        Link a manga to a collection, enforcing ownership.

        Verifies that the collection exists and is owned by `user_id`. If the link
        already exists, the method is a no-op.

        Args:
            user_id (uuid.UUID): Owner of the collection.
            collection_id (int): Target collection identifier.
            manga_id (int): Manga to add.

        Returns:
            None

        Raises:
            ValueError: If the collection does not exist or is not owned by the user.
            SQLAlchemyError: On DB errors (transaction rolled back and re-raised).
        '''
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

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error adding manga to collection: {e}", exc_info=True)
            raise

    async def remove_manga_from_collection(self, user_id: uuid.UUID, collection_id: int, manga_id: int) -> None:
        '''
        Remove a manga link from a user-owned collection.

        Verifies ownership and the existence of the link; raises if not present.

        Args:
            user_id (uuid.UUID): Owner of the collection.
            collection_id (int): Target collection identifier.
            manga_id (int): Manga to remove.

        Returns:
            None

        Raises:
            ValueError: If collection does not exist/owned, or link is missing.
            SQLAlchemyError: On DB errors (transaction rolled back and re-raised).
        '''
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

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error removing manga {manga_id} from collection {collection_id}: {e}", exc_info=True)
            raise

    async def get_manga_in_collection(self, user_id: uuid.UUID, collection_id: int) -> List[Manga]:
        '''
        List all manga contained in a user-owned collection.

        Args:
            user_id (uuid.UUID): Owner of the collection.
            collection_id (int): Target collection identifier.

        Returns:
            List[Manga]: All manga rows linked to the collection.

        Raises:
            ValueError: If the collection does not exist or is not owned by the user.
            SQLAlchemyError: On DB read errors (re-raised).
        '''
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
        
        except SQLAlchemyError as e:
            logger.error(f"Error fetching manga for collection {collection_id}: {e}", exc_info=True)
            raise

    async def is_manga_in_collection(self, collection_id: int, manga_id: int) -> bool:
        '''
        Check whether a manga is already linked to a collection.

        Args:
            collection_id (int): Collection to inspect.
            manga_id (int): Manga identifier.

        Returns:
            bool: True if the link exists; False on miss or on query failure.
        '''
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
