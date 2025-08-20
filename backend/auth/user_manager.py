import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, Request
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.schemas.user import UserCreate
from backend.dependencies import get_async_user_write_session

import logging
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)
load_dotenv()
SECRET = os.getenv("AUTH_SECRET")

if not SECRET:
    raise RuntimeError("AUTH_SECRET could not be found in environment variable")


async def get_user_db(session: AsyncSession = Depends(get_async_user_write_session)) -> AsyncGenerator:
    '''
    Generator that provides access to the DB for fastapi-users.
    '''
    yield SQLAlchemyUserDatabase(session, User)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    '''
    Manager utilized by fastapi-users. Handles user-related events such as registration, password resets, verification triggers.
    '''
    user_db_model = User
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    # What to do after a user registers
    async def on_after_register(self, user, request = None):
        logger.info(f"User {user.id} has registred.")
    
    # What to do after a user "forgets password"
    async def on_after_forgot_password(self, user, token, request = None):
        logger.info(f"User {user.id} requested a password reset. Token: {token}")

    # What to do after a user requests or needs a verification email.
    async def on_after_request_verify(self, user, token, request = None):
        logger.info(f"Verification Email Sent for user {user.id}. Token: {token}")

    async def update(self, user: User, update_dict: dict, safe: bool = False, request: Optional[Request] = None) -> User:
        
        if "displayname" in update_dict:
            logger.info(f"User {user.id} changed their displayname to: {update_dict['displayname']}")

        if "email" in update_dict:
            logger.info(f"User {user.id} is changing their eail to {update_dict['email']}")
            user.is_verified = False

        if "password" in update_dict:
            raw_password = update_dict.pop("password")
            update_dict["hashed_password"] = self.password_helper.hash(raw_password)
            logger.info(f"User {user.id} updated their password.")
        
        return await super().update(user, update_dict, safe=safe, request=request)


async def get_user_manager(user_db=Depends(get_user_db)):
    '''
    Generator that providcdes the UserManager to fastapi-users.
    '''
    yield UserManager(user_db)