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
        logger.info(f"Attempting to obtain simple profile summary for corresponding email: {email}")
        try:
            statement = select(Profile).where(Profile.email == email)

            result = await self.session.execute(statement)
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.error(f"Failed to fetch profile information via email for {email}: {str(e)}", exc_info=True)
            return None



