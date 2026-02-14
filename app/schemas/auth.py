"""Authentication schema objects."""

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginInput(BaseModel):
    """Validated login form payload."""

    username: str = Field(min_length=4, max_length=50)
    password: str = Field(min_length=1, max_length=128)
    csrf_token: str = Field(min_length=1, max_length=256)

    model_config = ConfigDict(str_strip_whitespace=True)


class CsrfInput(BaseModel):
    """Validated CSRF form payload."""

    csrf_token: str = Field(min_length=1, max_length=256)

    model_config = ConfigDict(str_strip_whitespace=True)
