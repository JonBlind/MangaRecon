'''
User manager and DB providers for FastAPI Users.

- Provides a DB generator bound to our async SQLAlchemy session.
- Implements user lifecycle hooks (register, forgot-password, verify).
'''

import uuid
from typing import AsyncGenerator
import jwt
from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users import BaseUserManager, UUIDIDMixin, exceptions
from fastapi_users.jwt import decode_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.user import User
from backend.dependencies import get_async_user_write_session
from backend.auth.config import settings
from backend.auth.email import (
    EmailDeliveryError,
    send_password_reset_email,
    send_verification_email,
)
from backend.rate_limit.account import (
    AccountRateLimitStorageError,
    account_rate_limiter,
)

import logging

logger = logging.getLogger(__name__)

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
    '''
    user_db_model = User
    reset_password_token_secret = settings.auth_secret
    verification_token_secret = settings.auth_secret
    reset_password_token_lifetime_seconds = (
        settings.password_reset_token_lifetime_minutes * 60
    )
    verification_token_lifetime_seconds = 259200   # 3 days

    async def _recipient_email_allowed(self, user) -> bool:
        """Reserve recipient capacity without exposing the email address."""
        try:
            decision = await account_rate_limiter.check_recipient(
                user.email
            )
        except AccountRateLimitStorageError:
            logger.exception(
                "Account email suppressed because recipient rate limiting "
                "failed for user %s.",
                user.id,
            )
            return False

        if decision.allowed:
            return True

        logger.info(
            "Account email suppressed by recipient rate limit for user %s "
            "(retry after %s seconds).",
            user.id,
            decision.retry_after,
        )
        return False

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
        logger.info("User %s registered.", user.id)

        try:
            await self.request_verify(user, request)
        except EmailDeliveryError:
            logger.exception(
                "Automatic verification email delivery failed for user %s.",
                user.id,
            )
    
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
        if not await self._recipient_email_allowed(user):
            return

        try:
            await send_password_reset_email(
                recipient=user.email,
                token=token,
            )
        except EmailDeliveryError:
            logger.exception(
                "Password-reset email delivery failed for user %s.",
                user.id,
            )
            return

        logger.info("Password reset requested for user %s.", user.id)

    async def validate_reset_password_token(self, token: str) -> User:
        """Validate a reset token without changing the user's password."""
        try:
            data = decode_jwt(
                token,
                self.reset_password_token_secret,
                [self.reset_password_token_audience],
            )
        except jwt.PyJWTError as exc:
            raise exceptions.InvalidResetPasswordToken() from exc

        try:
            user_id = data["sub"]
            password_fingerprint = data["password_fgpt"]
        except KeyError as exc:
            raise exceptions.InvalidResetPasswordToken() from exc

        try:
            parsed_id = self.parse_id(user_id)
        except exceptions.InvalidID as exc:
            raise exceptions.InvalidResetPasswordToken() from exc

        user = await self.get(parsed_id)
        valid_fingerprint, _ = self.password_helper.verify_and_update(
            user.hashed_password,
            password_fingerprint,
        )
        if not valid_fingerprint:
            raise exceptions.InvalidResetPasswordToken()

        if not user.is_active:
            raise exceptions.UserInactive()

        return user

    async def validate_password(self, password, user) -> None:
        """Apply MangaRecon's password policy to every password change."""
        if len(password) < 8:
            raise exceptions.InvalidPasswordException(
                reason="Password should be at least 8 characters."
            )

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
        if not await self._recipient_email_allowed(user):
            return

        await send_verification_email(
            recipient=user.email,
            token=token,
        )
        logger.info("Email verification requested for user %s.", user.id)

    async def on_after_verify(self, user, request = None):
        """Log successful ownership verification without exposing token data."""
        logger.info("Email verified for user %s.", user.id)

    async def on_after_reset_password(self, user, request = None):
        """Log a completed reset without exposing token data."""
        logger.info("Password reset completed for user %s.", user.id)


async def get_user_manager(user_db=Depends(get_user_db)):
    '''
    Dependency provider that yields a configured UserManager.

    Args:
        user_db (SQLAlchemyUserDatabase): User DB adapter bound to an async session.

    Yields:
        UserManager: Manager used by FastAPI Users to handle user logic.
    '''
    yield UserManager(user_db)
