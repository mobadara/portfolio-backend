from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import EmailStr, Field


class AdminUser(Document):
    username: str = Field(..., min_length=3, max_length=64)
    password_hash: str
    password_salt: str
    role: str = Field(default="admin")
    email: Optional[EmailStr] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "admin_users"


class ContactMessage(Document):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    subject: str = Field(default="", max_length=250)
    message: str = Field(..., min_length=1)
    status: str = Field(default="new")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "contact_messages"
