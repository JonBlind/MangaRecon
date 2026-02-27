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
from backend.utils.domain_exceptions import BadRequestError, ConflictError, NotFoundError

logger = logging.getLogger(__name__)

class ReadOnlyDatabaseError(RuntimeError):
    '''
    Error raised when a write is attempted through a read-only DB wrapper.
    '''
    pass


class ClientReadDatabase:
    '''
    Wraps an async SQLAlchemy `AsyncSession` and exposes **read-only**
    operations for profiles, ratings, and collections.

    Notes:
        - This wrapper does not expose write primitives (commit/add/delete).
        - Any route that depends on this type cannot write by accident.
    '''

    def __init__(self, session: AsyncSession):
        self._session = session

    # ====================
    # EXPOSED READ SESSION METHODS
    # ====================

    async def execute(self, stmt):
        '''
        Execute a SQLAlchemy statement on the underlying session.

        Args:
            stmt: SQLAlchemy statement (select/update/etc.).

        Returns:
            Result: SQLAlchemy Result object.
        '''
        return await self._session.execute(stmt)

    async def scalar_one_or_none(self, stmt):
        '''
        Execute a statement and return a single scalar row or None.

        Args:
            stmt: SQLAlchemy statement.

        Returns:
            Any | None: Scalar result if present, else None.
        '''
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def scalars_all(self, stmt):
        '''
        Execute a statement and return all scalar rows.

        Args:
            stmt: SQLAlchemy statement.

        Returns:
            list: List of scalar results.
        '''
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get(self, model, ident):
        '''
        Fetch an ORM object by primary key / identity.

        Args:
            model: ORM model class.
            ident: Primary key or identity tuple.

        Returns:
            Any | None: ORM instance if found, else None.
        '''
        return await self._session.get(model, ident)

    async def refresh(self, obj) -> None:
        '''
        Refresh an ORM object from the database.

        Note:
            Refresh does not mutate DB state; it is safe to expose on read wrapper.

        Args:
            obj: ORM instance to refresh.

        Returns:
            None
        '''
        await self._session.refresh(obj)

    # ====================
    # PROFILE (READ)
    # ====================

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
            result = await self.execute(stmt)
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
            result = await self.execute(stmt)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch user by identifier {identifier}: {str(e)}", exc_info=True)
            return None

    # ====================
    # RATINGS (READ)
    # ====================

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
            result = await self.execute(stmt)
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
            result = await self.execute(stmt)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error fetching all ratings for user {user_id}", exc_info=True)
            return []

    # ====================
    # COLLECTIONS (READ)
    # ====================

    async def get_manga_in_collection(self, user_id: uuid.UUID, collection_id: int) -> List[Manga]:
        '''
        List all manga contained in a user-owned collection.

        Args:
            user_id (uuid.UUID): Owner of the collection.
            collection_id (int): Target collection identifier.

        Returns:
            List[Manga]: All manga rows linked to the collection.

        Raises:
            NotFoundError: If the collection does not exist or is not owned by the user.
            SQLAlchemyError: On DB read errors (re-raised).
        '''
        try:
            # Confirm ownership
            result = await self.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

            # Fetch manga
            stmt = (
                select(Manga)
                .join(MangaCollection)
                .where(MangaCollection.collection_id == collection_id)
            )
            result = await self.execute(stmt)
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
            result = await self.execute(stmt)
            return result.scalar_one_or_none() is not None
        except SQLAlchemyError as e:
            logger.error(f"Failed to check if manga {manga_id} in collection {collection_id}", exc_info=True)
            return False


class ClientWriteDatabase(ClientReadDatabase):
    '''
    Wraps an async SQLAlchemy `AsyncSession` and exposes safe, user-facing
    operations for profiles, ratings, and collections. All mutating methods
    handle commit/rollback and log failures with context.

    Notes:
        - This wrapper includes commit/add/delete and other mutating helpers.
        - It extends `ClientReadDatabase`, so it can be used anywhere a read DB
          is expected, but not vice-versa.
    '''

    # ====================
    # EXPOSED WRITE SESSION METHODS
    # ====================

    async def commit(self) -> None:
        '''
        Commit the current transaction.

        Returns:
            None
        '''
        await self._session.commit()

    async def rollback(self) -> None:
        '''
        Roll back the current transaction.

        Returns:
            None
        '''
        await self._session.rollback()

    def add(self, obj) -> None:
        '''
        Add an ORM object to the current session.

        Args:
            obj: ORM instance to add.

        Returns:
            None
        '''
        self._session.add(obj)

    async def delete(self, obj) -> None:
        '''
        Delete an ORM object in the current session.

        Args:
            obj: ORM instance to delete.

        Returns:
            None
        '''
        await self._session.delete(obj)

    # ====================
    # PROFILE (WRITE)
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
            self.add(profile)
            await self.commit()
            await self.refresh(profile)
            return profile
        except SQLAlchemyError as e:
            await self.rollback()
            logger.error(f"Error creating profile: {str(e)}", exc_info=True)
            raise

    # ====================
    # RATINGS (WRITE)
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
            raise BadRequestError(code="SCORE_MISSING", message="Score is required.")
        clamped = max(0.0, min(10.0, float(score)))
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
            existing = await self.get(Rating, (user_id, manga_id))
            if existing:
                existing.personal_rating = score_norm
                logger.info(f"Updated rating: user_id={user_id}, manga_id={manga_id}, score={score_norm}")
                rating = existing
            else:
                rating = Rating(user_id=user_id, manga_id=manga_id, personal_rating=score_norm)
                self.add(rating)
                logger.info(f"Created new rating: user_id={user_id}, manga_id={manga_id}, score={score_norm}")

            await self.commit()
            await self.refresh(rating)
            return rating
        except SQLAlchemyError as e:
            await self.rollback()
            logger.error("Error saving rating", exc_info=True)
            raise

    async def delete_rating(self, user_id: uuid.UUID, manga_id: int) -> None:
        '''
        Delete the caller's rating for a manga.

        Args:
            user_id (uuid.UUID): User ID.
            manga_id (int): Manga ID.

        Raises:
            NotFoundError: If the rating doesn't exist.
        '''
        stmt = select(Rating).where(Rating.user_id == user_id, Rating.manga_id == manga_id)
        rating = (await self._session.execute(stmt)).scalar_one_or_none()
        if rating is None:
            raise NotFoundError(
                code="RATING_NOT_FOUND",
                message="Rating not found."
            )

        await self._session.delete(rating)
        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            raise

    # ====================
    # COLLECTIONS (WRITE)
    # ====================

    async def add_manga_to_collection(self, user_id: uuid.UUID, collection_id: int, manga_id: int) -> None:
        '''
        Link a manga to a collection, enforcing ownership.

        Verifies that the collection exists and is owned by `user_id`. If the link
        already exists, raises.

        Args:
            user_id (uuid.UUID): Owner of the collection.
            collection_id (int): Target collection identifier.
            manga_id (int): Manga to add.

        Returns:
            None

        Raises:
            NotFoundError: If the collection does not exist or is not owned by the user.
            ConflictError: If the manga is already in the collection.
            SQLAlchemyError: On DB errors (transaction rolled back and re-raised).
        '''
        try:
            result = await self.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

            exists = await self.execute(
                select(MangaCollection).where(
                    MangaCollection.collection_id == collection_id,
                    MangaCollection.manga_id == manga_id
                )
            )
            if exists.scalar_one_or_none():
                raise ConflictError(code="COLLECTION_MANGA_EXISTS",
                                    message="Manga is already in this collection.",
                                    detail={"collection_id": collection_id, "manga_id": manga_id})

            link = MangaCollection(collection_id=collection_id, manga_id=manga_id)
            self.add(link)
            await self.commit()

        except SQLAlchemyError as e:
            await self.rollback()
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
            NotFoundError: If collection does not exist/owned, or link is missing.
            SQLAlchemyError: On DB errors (transaction rolled back and re-raised).
        '''
        try:
            result = await self.execute(
                select(Collection).where(
                    Collection.collection_id == collection_id,
                    Collection.user_id == user_id
                )
            )
            collection = result.scalar_one_or_none()

            if not collection:
                raise NotFoundError(code="COLLECTION_NOT_FOUND", message="Collection not found.")

            stmt = select(MangaCollection).where(
                MangaCollection.collection_id == collection_id,
                MangaCollection.manga_id == manga_id
            )
            link_result = await self.execute(stmt)
            link = link_result.scalar_one_or_none()

            if not link:
                raise NotFoundError(code="COLLECTION_MANGA_NOT_FOUND", message="That manga is not in this collection.")

            await self.delete(link)
            await self.commit()

        except SQLAlchemyError as e:
            await self.rollback()
            logger.error(f"Error removing manga {manga_id} from collection {collection_id}: {e}", exc_info=True)
            raise
