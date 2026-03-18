from datetime import datetime, timezone
from typing import Dict, List, Optional

from beanie import Document
from pydantic import BaseModel, Field


class ProjectLinks(BaseModel):
	github: Optional[str] = None
	demo: Optional[str] = None
	youtube: Optional[str] = None
	paper: Optional[str] = None


class Project(Document):
	title: str = Field(..., min_length=1, max_length=180)
	description: str = Field(default="")
	fullDescription: Optional[str] = None
	category: str = Field(default="General")
	technologies: List[str] = Field(default_factory=list)
	techStack: List[str] = Field(default_factory=list)
	image: Optional[str] = None
	links: ProjectLinks = Field(default_factory=ProjectLinks)
	githubUrl: Optional[str] = None
	liveUrl: Optional[str] = None
	metrics: Dict[str, str] = Field(default_factory=dict)
	order: int = 0
	featured: bool = False
	created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
	updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

	class Settings:
		name = "projects"