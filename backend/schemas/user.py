import uuid
from pydantic import BaseModel, EmailStr, constr
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
    
    class Config:
        orm_mode = True
# Request
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: Annotated[str, constr(min_length=4)]
    displayname: Annotated[str, constr(min_length=4, max_length=64)]

    class Config:
        orm_mode = True

# Request    
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    displayname: Optional[Annotated[str, constr(min_length=4, max_length=64)]] = None

    class Config:
        orm_mode = True

# Request
# This is done when a user KNOWS their password, but still wants to change.
class ChangePassword(BaseModel):
    current_password: str
    new_password: str

    class Config:
        orm_mode = True

