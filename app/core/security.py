"""Security and password helper functions."""

from passlib.context import CryptContext

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""

    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plain password against stored hash."""

    return password_context.verify(password, password_hash)
