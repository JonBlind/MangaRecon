from fastapi_users.password import PasswordHelper

'''
Used by tests/factories and any internal code that needs to generate a hash
compatible with FastAPI-Users' password verification.
'''
_password_helper = PasswordHelper()


def hash_password(raw_password: str) -> str:
    return _password_helper.hash(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    verified, _updated_hash = _password_helper.verify_and_update(raw_password, hashed_password)
    return verified