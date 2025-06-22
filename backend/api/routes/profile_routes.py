from fastapi import APIRouter, Depends
import backend.schemas.profile as schemas
from backend.api.client_db import ClientDatabase
from backend.api.dependencies import get_db
from utils.response import success, error

router = APIRouter(prefix="/profile", tags=['Profile'])

@router.post("/")
async def create_profile(request: schemas.CreateProfileRequest,
                          db: ClientDatabase = Depends(lambda: get_db("user_write"))
                          ):
    
    '''
    Create a new user profile in the database.

    Accepts and requires the following validated input:
        - 'username'
        - 'displayname'
        - 'email'
        - 'password_hash'

    Databse persists the new profile and returns with the generated user_id if successful.

    Returns:
        dict: Standardized success/error response.
    '''
 
    return await db.create_profile(request.model_dump())

@router.get("/by-email")
async def get_profile_by_email(email:str,
                                db: ClientDatabase = Depends(lambda: get_db("user_read"))
                                ):
    
    '''
    Fetch basic user profile summary through their email address.

    Args:
        email (str): User's email address

    Returns:
        dict: user_id and display name if they exist, otherwise an error response.

    '''

    profile = await db.get_profile_by_email(email)
    if not profile:
        return error(message="Profile Not Found", detail="No profile exists with the given email.")
    
    return success(
        message = "Profile Found",
        data={"user_id" : profile.user_id, "displayname" : profile.displayname}
    )



