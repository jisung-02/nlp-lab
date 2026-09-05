"""Revocable admin sessions shared across application workers."""

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class AdminSession(SQLModel, table=True):
    __tablename__ = "admin_session"

    token_hash: str = Field(sa_column=Column(String(64), primary_key=True))
    admin_user_id: int = Field(foreign_key="admin_user.id", index=True)
    expires_at: int = Field(index=True)
    credential_hash: str = Field(sa_column=Column(String(64), nullable=False))
