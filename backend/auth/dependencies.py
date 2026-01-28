'''
Authentication-related dependencies for route protection.

Exposes:
- `fastapi_users`: typed FastAPI Users instance bound to our User model.
- `current_active_verified_user`: dependency ensuring a user is logged in,
  active, and email-verified before accessing a protected endpoint.
'''

import uuid
from fastapi_users import FastAPIUsers
from backend.db.models.user import User
from backend.auth.user_manager import get_user_manager
from backend.auth.config import auth_backend


# FastAPI Users instance for our UUID-keyed User model and JWT backend.
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager, [auth_backend]
)

# Protected: must be logged in + active + verified
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)

# Public/read-only routes: works without auth, but returns user when present
current_active_verified_user_optional = fastapi_users.current_user(optional=True, active=True, verified=True)