"""Security and password helper functions."""

import bcrypt


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""

    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed_password.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plain password against stored hash."""

    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
