import uuid
from pydantic import BaseModel, EmailStr, StringConstraints, ConfigDict
from datetime import datetime
from typing import Optional, Annotated

# Response
class UserRead(BaseModel):
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
    email: EmailStr
    password: str
    username: Annotated[str, StringConstraints(min_length=4)]
    displayname: Annotated[str, StringConstraints(min_length=4, max_length=64)]
    model_config = ConfigDict(from_attributes=True)

# Request    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    displayname: Optional[Annotated[str, StringConstraints(min_length=4, max_length=64)]] = None
    model_config = ConfigDict(from_attributes=True)

# Request
# This is done when a user KNOWS their password, but still wants to change.
class ChangePassword(BaseModel):
    current_password: str
    new_password: str
    model_config = ConfigDict(from_attributes=True)
