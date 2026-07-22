import uuid
from datetime import datetime
from typing import Optional, Annotated

from fastapi_users import schemas
from pydantic import BaseModel, Field, StringConstraints, ConfigDict, field_validator, ValidationInfo


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
    username: Annotated[str, StringConstraints(min_length=4, max_length=64, strip_whitespace=True)]
    displayname: Annotated[str, StringConstraints(min_length=4, max_length=64, strip_whitespace=True)]


class ProfileUpdate(BaseModel):
    '''
    Change profile information request for users who wish to change one of the following:
    - Username
    - Displayname
    '''
    model_config = ConfigDict(extra="forbid")
    username: Optional[Annotated[str, StringConstraints(min_length=4, max_length=64, strip_whitespace=True)]] = None
    displayname: Optional[Annotated[str, StringConstraints(min_length=4, max_length=64, strip_whitespace=True)]] = None

    @field_validator("username", "displayname")
    @classmethod
    def reject_explicit_null(cls, value: str | None, info: ValidationInfo) -> str:
        if value is None:
            raise ValueError(f"{info.field_name} cannot be null")
        return value

class ChangePassword(BaseModel):
    '''
    Change-password request for users who know their current password.
    Provides the current password and the desired new password.
    '''
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
