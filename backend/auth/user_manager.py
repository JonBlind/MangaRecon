'''
User manager and DB providers for FastAPI Users.

- Provides a DB generator bound to our async SQLAlchemy session.
- Implements user lifecycle hooks (register, forgot-password, verify).
- Customizes update behavior for display name, email, and password.
'''

import uuid
from typing import AsyncGenerator, Optional
from fastapi import Depends, Request
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.schemas.user import UserCreate
from backend.dependencies import get_async_user_write_session

import logging
from dotenv import load_dotenv
import os

logger = logging.getLogger(__name__)
SECRET = os.getenv("AUTH_SECRET")

if not SECRET:
    raise RuntimeError("AUTH_SECRET could not be found in environment variable")


async def get_user_db(session: AsyncSession = Depends(get_async_user_write_session)) -> AsyncGenerator:
    '''
    Yield a FastAPI Users SQLAlchemy adapter bound to the write session.

    Args:
        session (AsyncSession): Async SQLAlchemy session for user writes.

    Yields:
        SQLAlchemyUserDatabase: Adapter to perform user CRUD operations.
    '''
    yield SQLAlchemyUserDatabase(session, User)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    '''
    FastAPI Users user manager with UUID IDs and custom lifecycle hooks.

    Config:
        user_db_model: User ORM model.
        reset_password_token_secret (str): Secret for password reset tokens.
        verification_token_secret (str): Secret for email verification tokens.
        reset_password_token_lifetime_seconds (int): Reset token TTL (seconds).
        verification_token_lifetime_seconds (int): Verification token TTL (seconds).

    Notes:
        - Hooks log significant user events.
        - `update` is extended to handle display name, email re-verification,
          and password hashing before delegating to the base implementation.
    '''
    user_db_model = User
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    reset_password_token_lifetime_seconds = 7200      # 2 hours
    verification_token_lifetime_seconds = 259200   # 3 days

    # What to do after a user registers
    async def on_after_register(self, user, request = None):
        '''
        Hook invoked after successful registration.

        Args:
            user (User): Newly created user object.
            request (Request | None): Current request (if available).

        Returns:
            None
        '''
        logger.info(f"User {user.id} has registred.")
    
    # What to do after a user "forgets password"
    async def on_after_forgot_password(self, user, token, request = None):
        '''
        Hook invoked after a password reset is requested.

        Args:
            user (User): User requesting a reset.
            token (str): Generated reset token.
            request (Request | None): Current request (if available).

        Returns:
            None
        '''
        logger.info(f"User {user.id} requested a password reset. Token: {token}")

    # What to do after a user requests or needs a verification email.
    async def on_after_request_verify(self, user, token, request = None):
        '''
        Hook invoked when a verification email is (re)sent.

        Args:
            user (User): Target user.
            token (str): Verification token.
            request (Request | None): Current request (if available).

        Returns:
            None
        '''
        logger.info(f"Verification Email Sent for user {user.id}. Token: {token}")

    async def update(self, user: User, update_dict: dict, safe: bool = False, request: Optional[Request] = None) -> User:
        '''
        Update user fields with custom handling for display name, email, and password.

        - Logs a message when display name changes.
        - Marks the user as unverified if email changes.
        - Hashes plaintext `password` into `hashed_password` (and logs the event).

        Args:
            user (User): The user to update.
            update_dict (dict): Fields to update (may include 'displayname', 'email', 'password').
            safe (bool): If True, restricts updates to "safe" fields per FastAPI Users.
            request (Request | None): Current request (if available).

        Returns:
            User: The updated user.
        '''
        
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
    Dependency provider that yields a configured UserManager.

    Args:
        user_db (SQLAlchemyUserDatabase): User DB adapter bound to an async session.

    Yields:
        UserManager: Manager used by FastAPI Users to handle user logic.
    '''
    yield UserManager(user_db)