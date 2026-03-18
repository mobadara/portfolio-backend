from datetime import datetime, timezone
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..models.admin import AdminUser
from ..models.project import Project, ProjectLinks
from ..services.auth import get_current_admin

router = APIRouter()


class ProjectPayload(BaseModel):
	title: str = Field(..., min_length=1)
	description: str = ""
	fullDescription: Optional[str] = None
	category: Optional[str] = "General"
	technologies: List[str] = Field(default_factory=list)
	techStack: List[str] = Field(default_factory=list)
	image: Optional[str] = None
	links: Optional[Dict[str, Optional[str]]] = None
	githubUrl: Optional[str] = None
	liveUrl: Optional[str] = None
	metrics: Dict[str, str] = Field(default_factory=dict)
	order: int = 0
	featured: bool = False


def _normalize_tech_stack(payload: ProjectPayload) -> List[str]:
	source = payload.techStack or payload.technologies
	cleaned = [item.strip() for item in source if str(item).strip()]
	return cleaned


def _serialize_project(project: Project) -> dict:
	links = project.links.model_dump() if project.links else {}
	return {
		"id": str(project.id),
		"title": project.title,
		"description": project.description,
		"fullDescription": project.fullDescription,
		"category": project.category,
		"technologies": project.technologies,
		"techStack": project.techStack,
		"image": project.image,
		"links": links,
		"githubUrl": project.githubUrl or links.get("github"),
		"liveUrl": project.liveUrl or links.get("demo"),
		"metrics": project.metrics,
		"order": project.order,
		"featured": project.featured,
		"created_at": project.created_at.isoformat() if project.created_at else None,
		"updated_at": project.updated_at.isoformat() if project.updated_at else None,
	}


@router.get("/api/projects")
async def get_projects(category: Optional[str] = Query(default=None)):
	query = Project.find_all()
	if category:
		query = Project.find(Project.category == category)

	projects = await query.sort(+Project.order).to_list()
	return [_serialize_project(project) for project in projects]


@router.get("/api/projects/{project_id}")
async def get_project(project_id: str):
	project = await Project.get(PydanticObjectId(project_id))
	if not project:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
	return _serialize_project(project)


@router.get("/admin/projects")
async def get_admin_projects(_: AdminUser = Depends(get_current_admin)):
	projects = await Project.find_all().sort(+Project.order).to_list()
	return {"projects": [_serialize_project(project) for project in projects]}


@router.post("/admin/projects")
async def create_project(payload: ProjectPayload, _: AdminUser = Depends(get_current_admin)):
	normalized_stack = _normalize_tech_stack(payload)
	payload_links = payload.links or {}

	project = Project(
		title=payload.title,
		description=payload.description,
		fullDescription=payload.fullDescription,
		category=payload.category or "General",
		technologies=normalized_stack,
		techStack=normalized_stack,
		image=payload.image,
		links=ProjectLinks(
			github=payload_links.get("github") or payload.githubUrl,
			demo=payload_links.get("demo") or payload.liveUrl,
			youtube=payload_links.get("youtube"),
			paper=payload_links.get("paper"),
		),
		githubUrl=payload.githubUrl or payload_links.get("github"),
		liveUrl=payload.liveUrl or payload_links.get("demo"),
		metrics=payload.metrics,
		order=payload.order,
		featured=payload.featured,
		created_at=datetime.now(timezone.utc),
		updated_at=datetime.now(timezone.utc),
	)
	await project.insert()
	return _serialize_project(project)


@router.put("/admin/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectPayload, _: AdminUser = Depends(get_current_admin)):
	project = await Project.get(PydanticObjectId(project_id))
	if not project:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

	normalized_stack = _normalize_tech_stack(payload)
	payload_links = payload.links or {}

	project.title = payload.title
	project.description = payload.description
	project.fullDescription = payload.fullDescription
	project.category = payload.category or "General"
	project.technologies = normalized_stack
	project.techStack = normalized_stack
	project.image = payload.image
	project.links = ProjectLinks(
		github=payload_links.get("github") or payload.githubUrl,
		demo=payload_links.get("demo") or payload.liveUrl,
		youtube=payload_links.get("youtube"),
		paper=payload_links.get("paper"),
	)
	project.githubUrl = payload.githubUrl or payload_links.get("github")
	project.liveUrl = payload.liveUrl or payload_links.get("demo")
	project.metrics = payload.metrics
	project.order = payload.order
	project.featured = payload.featured
	project.updated_at = datetime.now(timezone.utc)

	await project.save()
	return _serialize_project(project)


@router.delete("/admin/projects/{project_id}")
async def delete_project(project_id: str, _: AdminUser = Depends(get_current_admin)):
	project = await Project.get(PydanticObjectId(project_id))
	if not project:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

	await project.delete()
	return {"status": "ok", "message": "Project deleted"}