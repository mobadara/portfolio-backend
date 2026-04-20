from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field

from ..models.admin import AdminUser, ContactMessage
from ..models.chat import ChatSession
from ..models.project import Project
from ..models.skill import Skill
from ..services.auth import (
    create_access_token,
    ensure_admin_role,
    get_current_admin,
    hash_password,
    verify_password,
)

router = APIRouter()
UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads"


def _ensure_uploads_dir() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _remove_previous(prefix: str) -> None:
    for existing_file in UPLOADS_DIR.glob(f"{prefix}.*"):
        existing_file.unlink(missing_ok=True)


def _extension_from_filename(filename: Optional[str]) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _latest_uploaded_file(prefix: str) -> Optional[Path]:
    _ensure_uploads_dir()
    candidates = sorted(
        UPLOADS_DIR.glob(f"{prefix}.*"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


async def _save_uploaded_file(file: UploadFile, destination: Path) -> int:
    content = await file.read()
    destination.write_bytes(content)
    return len(content)


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AdminCreateRequest(BaseModel):
    username: str = Field(..., min_length=3)
    email: Optional[EmailStr] = None
    role: str = "assistant"
    password: str = Field(..., min_length=6)


class AdminUpdateRequest(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    password: Optional[str] = Field(default=None, min_length=6)
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


class ContactMessageCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    subject: Optional[str] = ""
    message: str = Field(..., min_length=1)
    status: Optional[str] = "new"


class ContactMessageUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    status: Optional[str] = None


class BulkDeleteRequest(BaseModel):
    admin_password: str = Field(..., min_length=1)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize_admin(user: AdminUser) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": _to_iso(user.created_at),
        "updated_at": _to_iso(user.updated_at),
    }


def _serialize_message(message: ContactMessage) -> dict:
    return {
        "id": str(message.id),
        "name": message.name,
        "email": message.email,
        "subject": message.subject,
        "message": message.message,
        "status": message.status,
        "created_at": _to_iso(message.created_at),
        "updated_at": _to_iso(message.updated_at),
    }


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
        "created_at": _to_iso(project.created_at),
        "updated_at": _to_iso(project.updated_at),
    }


def _serialize_skill(skill: Skill) -> dict:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "level": skill.level,
        "category": skill.category,
        "icon": skill.icon,
        "order": skill.order,
        "created_at": _to_iso(skill.created_at),
        "updated_at": _to_iso(skill.updated_at),
    }


def _serialize_session(session: ChatSession) -> dict:
    last_activity = session.messages[-1].timestamp if session.messages else None
    preview = "No messages yet"
    if session.messages:
        preview = (session.messages[-1].content or "").strip() or "No messages yet"

    return {
        "session_id": session.session_id,
        "is_active": session.is_active,
        "human_mode": session.human_mode,
        "human_agent_assigned": session.human_agent_assigned,
        "cleared_by_user": session.cleared_by_user,
        "cleared_at": _to_iso(session.cleared_at),
        "created_at": _to_iso(session.created_at),
        "message_count": len(session.messages),
        "user_name": session.user_name,
        "user_email": str(session.user_email) if session.user_email else None,
        "user_phone": session.user_phone,
        "last_activity": _to_iso(last_activity),
        "last_message": preview,
        "is_read": bool(getattr(session, "is_read", False)),
        "is_archived": bool(getattr(session, "is_archived", False)),
    }


async def seed_default_admin() -> None:
    username = "mobadara"
    password = "Admin321."
    role = "admin"

    existing = await AdminUser.find_one(AdminUser.username == username)
    if existing:
        return

    password_hash, password_salt = hash_password(password)
    await AdminUser(
        username=username,
        password_hash=password_hash,
        password_salt=password_salt,
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ).insert()


@router.post("/admin/login")
@router.post("/admin/auth/login")
async def admin_login(payload: AdminLoginRequest):
    user = await AdminUser.find_one(AdminUser.username == payload.username)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash, user.password_salt):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})

    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
    }


@router.post("/admin/change-password")
async def change_password(payload: ChangePasswordRequest, current_admin: AdminUser = Depends(get_current_admin)):
    if not verify_password(payload.current_password, current_admin.password_hash, current_admin.password_salt):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    new_hash, new_salt = hash_password(payload.new_password)
    current_admin.password_hash = new_hash
    current_admin.password_salt = new_salt
    current_admin.updated_at = datetime.now(timezone.utc)
    await current_admin.save()

    return {"status": "ok", "message": "Password updated successfully"}


@router.get("/admin/users")
async def get_admin_users(_: AdminUser = Depends(get_current_admin)):
    users = await AdminUser.find_all().to_list()
    return {"users": [_serialize_admin(user) for user in users]}


@router.get("/admin/overview")
async def get_admin_overview(current_admin: AdminUser = Depends(get_current_admin)):
    users = await AdminUser.find_all().to_list()
    messages = await ContactMessage.find_all().sort([("created_at", -1)]).to_list()
    projects = await Project.find_all().sort(+Project.order).to_list()
    skills = await Skill.find_all().sort(+Skill.order).to_list()
    sessions = await ChatSession.find_all().sort([("created_at", -1)]).to_list()

    latest_resume = _latest_uploaded_file("resume")
    latest_portrait = _latest_uploaded_file("portrait")

    return {
        "status": "ok",
        "current_user": _serialize_admin(current_admin),
        "counts": {
            "users": len(users),
            "messages": len(messages),
            "projects": len(projects),
            "skills": len(skills),
            "sessions": len(sessions),
        },
        "users": [_serialize_admin(user) for user in users],
        "messages": [_serialize_message(item) for item in messages],
        "projects": [_serialize_project(project) for project in projects],
        "skills": [_serialize_skill(skill) for skill in skills],
        "sessions": [_serialize_session(session) for session in sessions],
        "assets": {
            "resume": {
                "filename": latest_resume.name if latest_resume else None,
                "url": f"/uploads/{latest_resume.name}" if latest_resume else None,
            },
            "portrait": {
                "filename": latest_portrait.name if latest_portrait else None,
                "url": f"/uploads/{latest_portrait.name}" if latest_portrait else None,
            },
        },
    }


@router.post("/admin/users")
async def create_admin_user(payload: AdminCreateRequest, _: AdminUser = Depends(get_current_admin)):
    existing = await AdminUser.find_one(AdminUser.username == payload.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")

    password_hash, password_salt = hash_password(payload.password)

    user = AdminUser(
        username=payload.username,
        email=payload.email,
        role=payload.role,
        password_hash=password_hash,
        password_salt=password_salt,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await user.insert()
    return _serialize_admin(user)


@router.put("/admin/users/{user_id}")
async def update_admin_user(user_id: str, payload: AdminUpdateRequest, _: AdminUser = Depends(get_current_admin)):
    user = await AdminUser.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.username is not None:
        user.username = payload.username
    if payload.email is not None:
        user.email = payload.email
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        password_hash, password_salt = hash_password(payload.password)
        user.password_hash = password_hash
        user.password_salt = password_salt

    user.updated_at = datetime.now(timezone.utc)
    await user.save()
    return _serialize_admin(user)


@router.delete("/admin/users/{user_id}")
async def delete_admin_user(user_id: str, current_admin: AdminUser = Depends(get_current_admin)):
    user = await AdminUser.get(PydanticObjectId(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if str(user.id) == str(current_admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account")

    await user.delete()
    return {"status": "ok", "message": "User deleted"}


@router.post("/contact")
async def create_contact_message(payload: ContactMessageCreateRequest):
    message = ContactMessage(
        name=payload.name,
        email=payload.email,
        subject=payload.subject or "",
        message=payload.message,
        status=payload.status or "new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await message.insert()
    return {"status": "ok", "message": "Contact message received", "id": str(message.id)}


@router.get("/admin/contact-messages")
async def get_contact_messages(_: AdminUser = Depends(get_current_admin)):
    messages = await ContactMessage.find_all().sort([("created_at", -1)]).to_list()
    return {"messages": [_serialize_message(item) for item in messages]}


@router.post("/admin/contact-messages")
async def create_contact_message_admin(
    payload: ContactMessageCreateRequest,
    _: AdminUser = Depends(get_current_admin)
):
    message = ContactMessage(
        name=payload.name,
        email=payload.email,
        subject=payload.subject or "",
        message=payload.message,
        status=payload.status or "new",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    await message.insert()
    return _serialize_message(message)


@router.put("/admin/contact-messages/{message_id}")
async def update_contact_message(
    message_id: str,
    payload: ContactMessageUpdateRequest,
    _: AdminUser = Depends(get_current_admin)
):
    message = await ContactMessage.get(PydanticObjectId(message_id))
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(message, key, value)

    message.updated_at = datetime.now(timezone.utc)
    await message.save()
    return _serialize_message(message)


@router.post("/admin/contact-messages/delete-all")
async def delete_all_contact_messages(
    payload: BulkDeleteRequest,
    current_admin: AdminUser = Depends(get_current_admin)
):
    ensure_admin_role(current_admin)

    if not verify_password(payload.admin_password, current_admin.password_hash, current_admin.password_salt):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password")

    messages = await ContactMessage.find_all().to_list()
    for message in messages:
        await message.delete()

    return {
        "status": "ok",
        "message": "All contact messages deleted",
        "total_deleted": len(messages)
    }


@router.delete("/admin/contact-messages/{message_id}")
async def delete_contact_message(message_id: str, _: AdminUser = Depends(get_current_admin)):
    message = await ContactMessage.get(PydanticObjectId(message_id))
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    await message.delete()
    return {"status": "ok", "message": "Message deleted"}


@router.post("/admin/upload/resume")
async def upload_latest_resume(
    file: UploadFile = File(...),
    _: AdminUser = Depends(get_current_admin),
):
    _ensure_uploads_dir()

    allowed_extensions = {".pdf", ".doc", ".docx"}
    extension = _extension_from_filename(file.filename)
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be a PDF, DOC, or DOCX file",
        )

    _remove_previous("resume")
    filename = f"resume{extension}"
    destination = UPLOADS_DIR / filename
    file_size = await _save_uploaded_file(file, destination)

    return {
        "status": "ok",
        "message": "Resume uploaded successfully",
        "filename": filename,
        "url": f"/uploads/{filename}",
        "size": file_size,
    }


@router.get("/api/assets/resume")
async def get_latest_resume_asset():
    latest_resume = _latest_uploaded_file("resume")
    if not latest_resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    return {
        "filename": latest_resume.name,
        "url": f"/uploads/{latest_resume.name}",
    }


@router.post("/admin/upload/portrait")
async def upload_latest_portrait(
    file: UploadFile = File(...),
    _: AdminUser = Depends(get_current_admin),
):
    _ensure_uploads_dir()

    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    extension = _extension_from_filename(file.filename)
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Portrait must be a JPG, JPEG, PNG, or WEBP image",
        )

    _remove_previous("portrait")
    filename = f"portrait{extension}"
    destination = UPLOADS_DIR / filename
    file_size = await _save_uploaded_file(file, destination)

    return {
        "status": "ok",
        "message": "Portrait uploaded successfully",
        "filename": filename,
        "url": f"/uploads/{filename}",
        "size": file_size,
    }


@router.get("/api/assets/portrait")
async def get_latest_portrait_asset():
    latest_portrait = _latest_uploaded_file("portrait")
    if not latest_portrait:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portrait not found")

    return {
        "filename": latest_portrait.name,
        "url": f"/uploads/{latest_portrait.name}",
    }
