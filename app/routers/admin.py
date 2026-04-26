from datetime import datetime, timezone
from typing import AsyncGenerator, Literal, Optional

from beanie import PydanticObjectId
from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from pydantic import BaseModel, EmailStr, Field

from ..models.admin import AdminUser, ContactMessage
from ..models.chat import ChatSession
from ..models.portfolio_asset import PortfolioAsset
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
ASSET_TYPE_VALUES: set[str] = {"resume", "portrait"}


def _normalize_asset_type(asset_type: str) -> str:
    normalized = str(asset_type or "").strip().lower()
    if normalized not in ASSET_TYPE_VALUES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="asset_type must be 'resume' or 'portrait'")
    return normalized


def _allowed_extensions_for(asset_type: str) -> set[str]:
    if asset_type == "resume":
        return {".pdf", ".doc", ".docx"}
    return {".jpg", ".jpeg", ".png", ".webp"}


def _extension_from_filename(filename: Optional[str]) -> str:
    if not filename:
        return ""
    if "." not in filename:
        return ""
    return f".{filename.rsplit('.', 1)[-1].lower()}"


def _safe_filename(filename: Optional[str], asset_type: str) -> str:
    extension = _extension_from_filename(filename)
    return f"{asset_type}{extension or ''}"


def _build_gridfs_bucket(request: Request) -> AsyncIOMotorGridFSBucket:
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database is not initialized")
    return AsyncIOMotorGridFSBucket(db)


async def _iter_gridfs_chunks(grid_out) -> AsyncGenerator[bytes, None]:
    while True:
        chunk = await grid_out.read(1024 * 1024)
        if not chunk:
            break
        yield chunk


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

    latest_resume = await PortfolioAsset.find_one(PortfolioAsset.asset_type == "resume")
    latest_portrait = await PortfolioAsset.find_one(PortfolioAsset.asset_type == "portrait")

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
                "filename": latest_resume.filename if latest_resume else None,
                "url": "/api/assets/resume" if latest_resume else None,
            },
            "portrait": {
                "filename": latest_portrait.filename if latest_portrait else None,
                "url": "/api/assets/portrait" if latest_portrait else None,
            },
        },
    }


@router.get("/admin/sessions")
async def get_chat_sessions(_: AdminUser = Depends(get_current_admin)):
    """Get all chat sessions with human_mode status - used by admin dashboard"""
    sessions = await ChatSession.find_all().sort([("created_at", -1)]).to_list()
    return {
        "status": "ok",
        "sessions": [_serialize_session(session) for session in sessions],
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


@router.post("/admin/upload/{asset_type}", response_class=PlainTextResponse)
async def upload_portfolio_asset(
    asset_type: Literal["resume", "portrait"],
    request: Request,
    file: UploadFile = File(...),
    _: AdminUser = Depends(get_current_admin),
):
    normalized_asset_type = _normalize_asset_type(asset_type)
    extension = _extension_from_filename(file.filename)
    allowed_extensions = _allowed_extensions_for(normalized_asset_type)

    if extension not in allowed_extensions:
        detail = "Resume must be a PDF, DOC, or DOCX file" if normalized_asset_type == "resume" else "Portrait must be a JPG, JPEG, PNG, or WEBP image"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

    bucket = _build_gridfs_bucket(request)
    existing_asset = await PortfolioAsset.find_one(PortfolioAsset.asset_type == normalized_asset_type)
    if existing_asset and existing_asset.file_id:
        try:
            await bucket.delete(ObjectId(existing_asset.file_id))
        except Exception:
            # Ignore stale references and continue with overwrite.
            pass

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    stored_filename = _safe_filename(file.filename, normalized_asset_type)
    gridfs_file_id = await bucket.upload_from_stream(
        stored_filename,
        file_bytes,
        metadata={
            "asset_type": normalized_asset_type,
            "content_type": file.content_type or "application/octet-stream",
        },
    )

    now = datetime.now(timezone.utc)
    if existing_asset:
        existing_asset.filename = stored_filename
        existing_asset.content_type = file.content_type or "application/octet-stream"
        existing_asset.file_id = str(gridfs_file_id)
        existing_asset.updated_at = now
        await existing_asset.save()
    else:
        await PortfolioAsset(
            filename=stored_filename,
            content_type=file.content_type or "application/octet-stream",
            asset_type=normalized_asset_type,
            file_id=str(gridfs_file_id),
            created_at=now,
            updated_at=now,
        ).insert()

    full_url = str(request.url_for("get_portfolio_asset", asset_type=normalized_asset_type))
    return PlainTextResponse(content=full_url)


@router.get("/api/assets/{asset_type}", name="get_portfolio_asset")
async def get_portfolio_asset(asset_type: Literal["resume", "portrait"], request: Request):
    normalized_asset_type = _normalize_asset_type(asset_type)
    asset = await PortfolioAsset.find_one(PortfolioAsset.asset_type == normalized_asset_type)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{normalized_asset_type.title()} not found")

    bucket = _build_gridfs_bucket(request)
    try:
        grid_out = await bucket.open_download_stream(ObjectId(asset.file_id))
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{normalized_asset_type.title()} file stream not found")

    headers = {"Content-Disposition": f"inline; filename=\"{asset.filename}\""}
    return StreamingResponse(
        _iter_gridfs_chunks(grid_out),
        media_type=asset.content_type or "application/octet-stream",
        headers=headers,
    )
