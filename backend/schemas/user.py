import uuid
from pydantic import BaseModel, EmailStr, StringConstraints, ConfigDict
from datetime import datetime
from typing import Optional, Annotated

# Response
class UserRead(BaseModel):
    '''
    Public profile fields for the authenticated user, including status flags
    and creation/login timestamps.
    '''
    id: uuid.UUID
    email: EmailStr
    username: str
    displayname:str
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

# Request
class UserCreate(BaseModel):
    '''
    Registration payload for a new user account, including email, password,
    and initial profile fields.
    '''
    email: EmailStr
    password: str
    username: Annotated[str, StringConstraints(min_length=4)]
    displayname: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    model_config = ConfigDict(from_attributes=True)

# Request    
class UserUpdate(BaseModel):
    '''
    Partial update for user profile fields. Only provided fields are modified.
    '''
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    displayname: Optional[Annotated[str, StringConstraints(min_length=4, max_length=64)]] = None
    model_config = ConfigDict(from_attributes=True)

# Request
# This is done when a user KNOWS their password, but still wants to change.
class ChangePassword(BaseModel):
    '''
    Change-password request for users who know their current password.
    Provides the current password and the desired new password.
    '''
    current_password: str
    new_password: str
    model_config = ConfigDict(from_attributes=True)
