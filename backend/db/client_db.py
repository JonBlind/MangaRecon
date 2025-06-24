from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from backend.db.models import Profile, Rating, Collection
from typing import Dict, Any, List, Optional
import logging
from backend.utils.response import success, error

logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)


class ClientDatabase:
    def __init__(self, session: AsyncSession):
        '''
        Instance of a user_faced client that interfaces with the database.
        Only includes generic functions that alter the database based on USER interactions.

        Args:
            session (AsyncSession):
        '''
        self.session = session

    # ==============
    # PROFILE
    # ==============
    
    async def create_profile(self, data:dict):
        '''
        Create a profile with the provided data.
        '''
        logger.info(f"Attempting to create profile for corresponding email: {data.get('email')}")
        try:
            profile = Profile(**data) # In python, doing ** lets you unpack an arbitrary number of keys in a key_value structure. So we do this to easily unpack data into profile.
            self.session.add(profile)
            await self.session.commit()
            await self.session.refresh(profile)

            logger.info(f"Successffully created profile with user_id: {profile.user_id}")
            
            return success(
                message="Profile Created Successfully",
                data={"user_id": profile.user_id}
            )
        
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating profile: {str(e)}", exc_info=True)
            
            return error(
                message="Failed to create Profile",
                detail=str(e)
            )

    async def get_profile_by_email(self, email:str) -> Optional[Profile]:
        '''
        Fetches a user with either their EMAIL or USERNAME
        '''

        logger.info(f"Attempting to obtain simple profile summary for corresponding email: {email}")
        try:
            statement = select(Profile).where(Profile.email == email)

            result = await self.session.execute(statement)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch profile information via email for {email}: {str(e)}", exc_info=True)
            return None
        
    async def get_profile_by_identifier(self, identifier:str) -> Optional[Profile]:
        '''
        Fetches a user with either their EMAIL or USERNAME
        '''

        logger.info(f"Attempting to obtain simple profile summary for corresponding identifier: {identifier}")
        try:
            statement = select(Profile).where(
                (Profile.username == identifier) | (Profile.email == identifier)
                )

            result = await self.session.execute(statement)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch profile information via identifier for {identifier}: {str(e)}", exc_info=True)
            return None

    # ==============
    # Ratings
    # ==============

    async def rate_manga(self, user_id: int, manga_id: int, score: float) -> dict:
        '''
        Create or update a rating for a given manga by the provided user
        '''

        try:
            existing = await self.session.get(Rating, (user_id, manga_id))

            if existing:
                existing.personal_rating = score
                logger.info(f"Updated Rating: user_id={user_id}, manga_id={manga_id}, new_score={score}")
            else:
                rating = Rating(user_id=user_id, manga_id=manga_id, personal_rating=score)
                self.session.add(rating)
                logger.info(f"Created new rating: user_id={user_id}, manga_id={manga_id}, new_score={score}")
            
            await self.session.commit()
            return success(message="Rating Saved", data={"user_id": user_id, "manga_id": manga_id, "rating": score})
        
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error("Error saving manga rating", exc_info=True)
            return error(message="Failed to save rating.", detail=str(e))
        
    async def get_user_rating_for_manga(self, user_id: int, manga_id: int) -> Optional[Rating]:
        '''
        Grab the rating for a specified manga of the given user. Returns None if nothing is found.
        '''
        try:
            statement = select(Rating).where(Rating.user_id == user_id, Rating.manga_id == manga_id)
            result = await self.session.execute(statement)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Error grabbing manga rating for user: {user_id}, manga: {manga_id}", exc_info=True)
            return None
    
    async def get_all_user_ratings(self, user_id: int) -> List[Rating]:
        '''
        Grab ALL manga ratings that the specified user has. 
        '''
        try:
            statement = select(Rating).where(Rating.user_id == user_id)
            result = await self.session.execute(statement)
            return result.scalars().all()
        except SQLAlchemyError as e:
            logger.error(f"Error grabbing all manga ratings for user: {user_id}", exc_info=True)
            return None
