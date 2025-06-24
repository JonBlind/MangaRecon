import uuid
from fastapi_users import FastAPIUsers
from backend.db.models.user import User
from backend.auth.user_manager import get_user_manager
from backend.auth.config import auth_backend

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend]
)

# This varaible establishes the current user.
# Ensures the user is flagged as: 'active' and 'verified' before allowing them to continue.
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)