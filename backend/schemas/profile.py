from pydantic import BaseModel, EmailStr

class CreateProfileRequest(BaseModel):
    username: str
    displayname: str
    email: EmailStr
    password: str # not hashed yet

class LoginRequest(BaseModel):
    # identifier is either Email or Username
    identifier: str
    password: str