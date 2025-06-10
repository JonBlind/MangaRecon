from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from backend.db.models import Profile, Rating, Collection
from typing import Dict, Any, List, Optional
import logging

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
    
    async def create_profile(self, data):
        logger.info(f"Attempting to create profile for corresponding email: {data.get('email')}")



