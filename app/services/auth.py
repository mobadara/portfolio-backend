import hashlib
import os
import secrets
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from itsdangerous import BadData, SignatureExpired, URLSafeTimedSerializer

from ..models.admin import AdminUser

logger = logging.getLogger(__name__)


security = HTTPBearer(auto_error=False)


def _get_secret_key() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("ADMIN_AUTH_TOKEN") or "portfolio-admin-secret"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key=_get_secret_key(), salt="admin-auth")


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    used_salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), used_salt.encode("utf-8"), 120_000)
    return derived.hex(), used_salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate, password_hash)


def create_access_token(payload: Dict[str, Any]) -> str:
    token_payload = {
        **payload,
        "iat": int(datetime.now(timezone.utc).timestamp())
    }
    return _serializer().dumps(token_payload)


def decode_access_token(token: str, max_age_seconds: int = 60 * 60 * 24 * 7) -> Dict[str, Any]:
    try:
        data = _serializer().loads(token, max_age=max_age_seconds)
        if not isinstance(data, dict):
            raise ValueError("Invalid token payload")
        return data
    except SignatureExpired as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except (BadData, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AdminUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")

    raw_token = credentials.credentials

    static_admin_token = os.getenv("ADMIN_AUTH_TOKEN", "")
    if static_admin_token and secrets.compare_digest(raw_token, static_admin_token):
        fallback_username = os.getenv("ADMIN_USERNAME", "mobadara")
        admin_user = await AdminUser.find_one(AdminUser.username == fallback_username)
        if admin_user:
            return admin_user

    data = decode_access_token(raw_token)
    user_id = data.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    admin_user = await AdminUser.get(user_id)
    if not admin_user or not admin_user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account not found")

    return admin_user


async def get_admin_from_token_value(token: str) -> Optional[AdminUser]:
    if not token:
        logger.debug("🔍 DEBUG: Token is empty/None")
        return None

    static_admin_token = os.getenv("ADMIN_AUTH_TOKEN", "")
    logger.debug(f"🔍 DEBUG: Checking token. Static token exists: {bool(static_admin_token)}")
    
    if static_admin_token and secrets.compare_digest(token, static_admin_token):
        logger.info(f"✅ DEBUG: Token matches static ADMIN_AUTH_TOKEN")
        fallback_username = os.getenv("ADMIN_USERNAME", "mobadara")
        admin = await AdminUser.find_one(AdminUser.username == fallback_username)
        logger.info(f"✅ DEBUG: Found admin user: {admin.username if admin else 'NOT FOUND'}")
        return admin

    logger.debug(f"🔍 DEBUG: Token doesn't match static token. Length: {len(token)}. Trying JWT decode...")
    try:
        data = decode_access_token(token)
        logger.info(f"✅ DEBUG: JWT token decoded successfully")
    except HTTPException as e:
        logger.warning(f"❌ DEBUG: JWT decode failed: {e.detail}")
        return None

    user_id = data.get("sub")
    if not user_id:
        logger.warning(f"❌ DEBUG: No user_id in JWT claims")
        return None

    try:
        admin = await AdminUser.get(user_id)
        logger.info(f"✅ DEBUG: Found admin user by ID: {admin.username if admin else 'NOT FOUND'}")
        return admin
    except Exception as e:
        logger.warning(f"❌ DEBUG: Failed to get admin user by ID: {e}")
        return None


def ensure_admin_role(admin_user: AdminUser) -> None:
    role = str(admin_user.role or "").strip().lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action"
        )
