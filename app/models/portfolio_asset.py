from datetime import datetime, timezone
from typing import Literal

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class PortfolioAsset(Document):
    filename: str = Field(..., min_length=1)
    content_type: str = Field(..., min_length=1)
    asset_type: Literal["resume", "portrait"]
    file_id: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "portfolio_assets"
        indexes = [
            IndexModel("asset_type", unique=True),
        ]
