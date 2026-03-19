from datetime import datetime, timezone
from typing import Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..models.admin import AdminUser, ContactMessage
from ..services.auth import (
    create_access_token,
    ensure_admin_role,
    get_current_admin,
    hash_password,
    verify_password,
)

router = APIRouter()


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
