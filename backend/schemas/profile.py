from pydantic import BaseModel, EmailStr

class CreateProfileRequest(BaseModel):
    username: str
    displayname: str
    email: EmailStr
    password_hash: str