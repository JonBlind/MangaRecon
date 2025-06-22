from fastapi import APIRouter, Depends
import backend.schemas.profile as schemas
from backend.api.client_db import ClientDatabase
from backend.api.dependencies import get_db
from utils.response import success, error
from backend.utils.auth_utils import verify_password
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login")
async def login(
    request: schemas.LoginRequest,
    db: ClientDatabase = Depends(lambda: get_db("user_read"))
):
    '''
    Attempts to login a user based on the inputted fields.

    Returns:
        dict: Standardized success or error response.
    '''
    try:
        profile = await db.get_profile_by_identifier(request.identifier)

        if not profile:
            return error(message="Login Failed", detail="User not found.")
        
        if not verify_password(request.password, profile.password_hash):
            return error(message="Login Failed", detail="Incorrect Password")
        
        return success(
            message="Login Successful",
            data={"user_id": profile.user_id, "username": profile.username}
        )
    
    except Exception:
        logger.error(f"Unexpected Error During Login.", exc_info=True)
        return error(message="Internal Server Error", detail="Login process failed.")