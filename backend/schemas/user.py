import uuid
from datetime import datetime
from typing import Optional, Annotated

from fastapi_users import schemas
from pydantic import EmailStr, Field, StringConstraints


class UserRead(schemas.BaseUser[uuid.UUID]):
    '''
    Public profile fields for the authenticated user, including status flags
    and creation/login timestamps.
    '''
    username: str
    displayname: str
    created_at: datetime
    last_login: Optional[datetime] = None


class UserCreate(schemas.BaseUserCreate):
    '''
    Registration payload for a new user account, including email, password,
    and initial profile fields.
    '''
    # password included w/ BaseUserCreate
    password: Annotated[str, StringConstraints(min_length=8)]
    username: Annotated[str, StringConstraints(min_length=4)]
    displayname: Annotated[str, StringConstraints(min_length=4, max_length=64)]


class UserUpdate(schemas.BaseUserUpdate):
    '''
    Partial update for user profile fields. Only provided fields are modified.
    '''
    # email + password ARE OPTIONAL and included w/ BaseUserCreate
    displayname: Optional[Annotated[str, StringConstraints(min_length=4, max_length=64)]] = None
    username: Optional[Annotated[str, StringConstraints(min_length=4)]] = None


class ChangePassword(schemas.BaseModel):
    '''
    Change-password request for users who know their current password.
    Provides the current password and the desired new password.
    '''
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
