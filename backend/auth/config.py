import os
from dotenv import load_dotenv
from fastapi_users.authentication import CookieTransport, JWTStrategy, AuthenticationBackend

load_dotenv()

SECRET = os.getenv("AUTH_SECRET")
if not SECRET:
    raise RuntimeError("AUTH_SECRET not found in environment")

cookie_transport = CookieTransport(cookie_name="auth", cookie_max_age=3600)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)