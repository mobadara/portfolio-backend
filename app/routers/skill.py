from datetime import datetime, timezone

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..models.admin import AdminUser
from ..models.skill import Skill
from ..services.auth import get_current_admin

router = APIRouter()


class SkillPayload(BaseModel):
    name: str = Field(..., min_length=1)
    level: int = Field(..., ge=0, le=100)
    category: str = Field(..., min_length=1)
    icon: str = Field(default="star", min_length=1)
    order: int = Field(default=0)


def _serialize_skill(skill: Skill) -> dict:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "level": skill.level,
        "category": skill.category,
        "icon": skill.icon,
        "order": skill.order,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }


@router.get("/api/skills")
async def get_public_skills():
    skills = await Skill.find_all().sort(+Skill.order).to_list()
    return [_serialize_skill(skill) for skill in skills]


@router.get("/admin/skills")
async def get_admin_skills(_: AdminUser = Depends(get_current_admin)):
    skills = await Skill.find_all().sort(+Skill.order).to_list()
    return {"skills": [_serialize_skill(skill) for skill in skills]}


@router.post("/admin/skills")
async def create_skill(payload: SkillPayload, _: AdminUser = Depends(get_current_admin)):
    skill = Skill(
        name=payload.name.strip(),
        level=payload.level,
        category=payload.category.strip(),
        icon=payload.icon.strip(),
        order=payload.order,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await skill.insert()
    return _serialize_skill(skill)


@router.put("/admin/skills/{skill_id}")
async def update_skill(skill_id: str, payload: SkillPayload, _: AdminUser = Depends(get_current_admin)):
    skill = await Skill.get(PydanticObjectId(skill_id))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    skill.name = payload.name.strip()
    skill.level = payload.level
    skill.category = payload.category.strip()
    skill.icon = payload.icon.strip()
    skill.order = payload.order
    skill.updated_at = datetime.now(timezone.utc)

    await skill.save()
    return _serialize_skill(skill)


@router.delete("/admin/skills/{skill_id}")
async def delete_skill(skill_id: str, _: AdminUser = Depends(get_current_admin)):
    skill = await Skill.get(PydanticObjectId(skill_id))
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    await skill.delete()
    return {"status": "ok", "message": "Skill deleted"}
