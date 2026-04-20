from datetime import datetime, timezone

from beanie import Document
from pydantic import Field


class Skill(Document):
    name: str = Field(..., min_length=1, max_length=120)
    level: int = Field(default=50, ge=0, le=100)
    category: str = Field(default="General", min_length=1, max_length=120)
    icon: str = Field(default="star", min_length=1, max_length=80)
    order: int = Field(default=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "skills"
