import bcrypt
import logging

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    '''
    Hashes a plain-text password using bcrypt.

    Args:
        password (str): raw password to hash.

    Returns:
        str: A bcrypt-hashed password.
    '''

    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8", salt))
        return hashed.decode("utf-8")
    
    except Exception as e:
        # DO NOT PRINT THAT EXCEPTION.
        logger.error(f"Failed to Hash password.", exc_info=True)
        raise


def verify_password(password: str, hashed: str) -> bool:
    '''
    Verifies that a plain-text password matches a stored bcrypt hash.

    Args:
        password (str): Password to check.
        hashed (str): Bcrypt hash to compare the password against.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    '''

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception as e:
        # DO NOT PRINT EXCEPTION WITH PLAINTEXT PASSWORDS
        logger.error("Password Verification Ran Into An Error!", exc_info=True)
        return False