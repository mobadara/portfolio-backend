from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from groq import Groq
from typing import cast, Optional
import os
import logging
import json
import re
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from ..models.chat import ChatSession, Message, MessageRole
from ..models.admin import AdminUser
from ..services.auth import ensure_admin_role, get_admin_from_token_value, get_current_admin, verify_password
from ..services.websocket_manager import manager
from ..services.email import send_lead_notification, send_session_deleted_notification
from ..services.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()


class BulkDeleteRequest(BaseModel):
    admin_password: str = Field(..., min_length=1)


def _extract_human_support_payload(data: str) -> Optional[dict]:
    """Extract human-support payload from structured JSON or legacy text format."""
    try:
        parsed = json.loads(data)
        if isinstance(parsed, dict) and parsed.get("type") == "HUMAN_SUPPORT_REQUEST":
            return {
                "name": (parsed.get("name") or "").strip(),
                "email": (parsed.get("email") or "").strip(),
                "phone": (parsed.get("phone") or "").strip(),
                "message": (parsed.get("message") or "").strip(),
                "schema": parsed.get("schema"),
                "version": parsed.get("version")
            }
    except json.JSONDecodeError:
        pass

    if not data.startswith("HUMAN_SUPPORT_REQUEST"):
        return None

    body = data.split("\n", 1)[1] if "\n" in data else ""
    name_match = re.search(r"name\s*:\s*(.+)", body, re.IGNORECASE)
    email_match = re.search(r"email\s*:\s*(.+)", body, re.IGNORECASE)
    phone_match = re.search(r"phone\s*:\s*(.+)", body, re.IGNORECASE)

    return {
        "name": name_match.group(1).strip() if name_match else "",
        "email": email_match.group(1).strip() if email_match else "",
        "phone": phone_match.group(1).strip() if phone_match else "",
        "message": body.strip(),
        "schema": "legacy_human_support",
        "version": 1
    }


def _is_valid_email(email: str) -> bool:
    if not email:
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _extract_json_payload(raw_data: str) -> Optional[dict]:
    try:
        parsed = json.loads(raw_data)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


def _to_ws_base(url: str) -> str:
    if not url:
        return ""
    return url.replace("https://", "wss://").replace("http://", "ws://")


async def _mark_session_cleared(session: ChatSession) -> None:
    session.messages = []
    session.is_active = False
    session.cleared_by_user = True
    session.cleared_at = datetime.now(timezone.utc)
    session.human_mode = False
    session.human_agent_assigned = False
    await session.save()


@router.get("/admin/sessions")
async def get_admin_sessions(_: AdminUser = Depends(get_current_admin)):
    """List all active chat sessions with basic info"""
    sessions = await ChatSession.find_all().to_list()
    
    sessions_list = []
    for session in sessions:
        sessions_list.append({
            "session_id": session.session_id,
            "is_active": session.is_active,
            "human_mode": session.human_mode,
            "human_agent_assigned": session.human_agent_assigned,
            "cleared_by_user": session.cleared_by_user,
            "cleared_at": session.cleared_at,
            "created_at": session.created_at,
            "message_count": len(session.messages),
            "user_name": session.user_name,
            "user_email": session.user_email,
            "last_activity": session.messages[-1].timestamp if session.messages else None
        })
    
    return {
        "status": "ok",
        "total_sessions": len(sessions_list),
        "sessions": sessions_list
    }


def _get_groq_client() -> Optional[Groq]:
    """Lazily initialize Groq client only if API key is set"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("Groq API key not configured (GROQ_API_KEY env var required)")
        return None
    
    try:
        return Groq(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {str(e)}")
        return None


@router.get("/admin/chat_sessions/{session_id}")
async def get_admin_chat_session(session_id: str, _: AdminUser = Depends(get_current_admin)):
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        return {"status": "not_found", "session_id": session_id}

    backend_url = os.getenv("BACKEND_URL", "https://portfolio-backend-tjq3.onrender.com").rstrip("/")
    derived_ws_base = _to_ws_base(backend_url)
    admin_ws_base = _to_ws_base(os.getenv("ADMIN_WS_BASE", derived_ws_base).rstrip("/"))
    admin_ws_url = f"{admin_ws_base}/ws/admin/{session_id}"

    return {
        "status": "ok",
        "session_id": session_id,
        "is_active": session.is_active,
        "human_mode": session.human_mode,
        "cleared_by_user": session.cleared_by_user,
        "cleared_at": session.cleared_at,
        "messages": session.model_dump().get("messages", []),
        "admin_websocket": {
            "url": admin_ws_url,
            "token_required": True,
            "token_env": "ADMIN_AUTH_TOKEN"
        }
    }


@router.get("/chat/{session_id}/status")
async def get_chat_session_status(session_id: str):
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        return {
            "status": "not_found",
            "session_id": session_id,
            "exists": False
        }

    return {
        "status": "ok",
        "session_id": session_id,
        "exists": True,
        "is_active": session.is_active,
        "human_mode": session.human_mode,
        "cleared_by_user": session.cleared_by_user
    }


@router.post("/chat/{session_id}/clear")
async def clear_chat_session(session_id: str):
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        return {
            "status": "not_found",
            "session_id": session_id
        }

    await _mark_session_cleared(session)
    await manager.forward_to_admin(
        session_id,
        json.dumps({
            "type": "session_cleared",
            "session_id": session_id,
            "cleared_by": "user",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    )

    return {
        "status": "ok",
        "session_id": session_id,
        "cleared_by_user": True,
        "message": "Session cleared by user"
    }


@router.post("/chat/{session_id}/request-human")
async def request_human_mode(session_id: str):
    """Enable human mode for a session - user requests to speak with a human"""
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    
    if not session:
        return {
            "status": "error",
            "message": "Session not found",
            "session_id": session_id
        }
    
    # Enable human mode
    session.human_mode = True
    session.human_agent_assigned = False  # Mark as pending assignment
    await session.save()
    
    # Send notification email
    try:
        lead_dict = {
            "name": session.user_name or "Chat User",
            "email": session.user_email or "Not provided",
            "phone": session.user_phone or "Human assistance requested"
        }
        await send_lead_notification(lead_dict, session_id)
        logger.info(f"Human mode requested for session {session_id}, notification sent")
    except Exception as e:
        logger.error(f"Failed to send notification for session {session_id}: {str(e)}")
    
    # Notify user and admin via WebSocket if connected
    user_message = "I'm connecting you with Muyiwa now. He'll be with you shortly! 👋"
    await manager.forward_to_user(session_id, user_message)
    await manager.forward_to_admin(session_id, f"User requested human assistance in session {session_id}")
    
    return {
        "status": "ok",
        "message": "Human mode enabled",
        "session_id": session_id,
        "human_mode": True
    }


@router.delete("/admin/chat_sessions/{session_id}")
async def delete_chat_session(session_id: str, _: AdminUser = Depends(get_current_admin)):
    """Admin endpoint to delete a chat session"""
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        return {"status": "not_found", "session_id": session_id}

    user_email = str(session.user_email) if session.user_email else ""

    delete_event = json.dumps({
        "type": "session_deleted",
        "session_id": session_id,
        "deleted_by": "admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": "This chat session was deleted by the admin team."
    })

    await manager.forward_to_user(session_id, delete_event)
    await manager.forward_to_admin(session_id, delete_event)

    if user_email:
        try:
            await send_session_deleted_notification(user_email, session_id)
        except Exception as exc:
            logger.error(f"Failed to send session deletion email for {session_id}: {str(exc)}")
    
    await session.delete()
    await manager.close_session_connections(session_id)
    
    logger.info(f"Chat session {session_id} deleted by admin")
    return {"status": "ok", "message": f"Session {session_id} deleted"}


@router.delete("/admin/chat_sessions")
async def delete_all_chat_sessions(current_admin: AdminUser = Depends(get_current_admin)):
    ensure_admin_role(current_admin)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Use /admin/chat_sessions/delete-all with admin password confirmation"
    )


@router.post("/admin/chat_sessions/delete-all")
async def delete_all_chat_sessions_secure(
    payload: BulkDeleteRequest,
    current_admin: AdminUser = Depends(get_current_admin)
):
    ensure_admin_role(current_admin)

    admin_password = payload.admin_password

    if not verify_password(admin_password, current_admin.password_hash, current_admin.password_salt):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin password")

    sessions = await ChatSession.find_all().to_list()
    for session in sessions:
        delete_event = json.dumps({
            "type": "session_deleted",
            "session_id": session.session_id,
            "deleted_by": "admin",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": "This chat session was deleted by the admin team."
        })
        await manager.forward_to_user(session.session_id, delete_event)
        await manager.forward_to_admin(session.session_id, delete_event)
        await session.delete()
        await manager.close_session_connections(session.session_id)

    logger.info("All chat sessions deleted by admin (secure endpoint)")
    return {"status": "ok", "message": "All sessions deleted", "total_deleted": len(sessions)}


@router.websocket("/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    client = _get_groq_client()
    if not client:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        logger.error(f"Groq client not available for session {session_id}")
        return
    
    await manager.connect(websocket, session_id)
    
    # 1. Load or Create Session in DB
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        session = ChatSession(
            session_id=session_id,
            user_name=None,
            user_email=None,
            user_phone=None
        )
        # Add system prompt implicitly to history context (not DB) for AI
        await session.insert()

    try:
        while True:
            # 2. Receive User Message
            raw_data = await websocket.receive_text()
            payload = _extract_json_payload(raw_data)

            if payload and payload.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}),
                    websocket
                )
                continue

            if payload and payload.get("type") == "clear_chat":
                await _mark_session_cleared(session)
                clear_event = {
                    "type": "session_cleared",
                    "session_id": session_id,
                    "cleared_by": "user",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await manager.send_personal_message(json.dumps(clear_event), websocket)
                await manager.forward_to_admin(session_id, json.dumps(clear_event))
                continue

            if payload and payload.get("type") == "audio":
                audio_base64 = str(payload.get("audio_base64") or "").strip()
                if not audio_base64:
                    continue

                audio_payload = {
                    "type": "audio",
                    "role": "user",
                    "audio_base64": audio_base64,
                    "mime_type": payload.get("mime_type") or "audio/webm",
                    "duration_seconds": payload.get("duration_seconds"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                user_msg = Message(role=MessageRole.USER, content=json.dumps(audio_payload))
                session.messages.append(user_msg)
                await session.save()

                await manager.forward_to_admin(session_id, json.dumps(audio_payload))
                continue

            if payload and payload.get("type") == "message":
                data = str(payload.get("content") or "").strip()
            else:
                data = raw_data

            if not data.strip():
                continue

            human_payload = _extract_human_support_payload(data)
            if human_payload:
                captured_name = human_payload.get("name") or "Visitor"
                captured_email = human_payload.get("email") or "Not provided"
                captured_phone = human_payload.get("phone") or "Not provided"

                details_message = human_payload.get("message") or (
                    f"Human support details:\n"
                    f"- Name: {captured_name}\n"
                    f"- Email: {captured_email}\n"
                    f"- Phone: {captured_phone}"
                )

                user_msg = Message(role=MessageRole.USER, content=details_message)
                session.messages.append(user_msg)

                session.user_name = captured_name if captured_name and captured_name != "Not provided" else session.user_name
                session.user_phone = captured_phone if captured_phone and captured_phone != "Not provided" else session.user_phone

                if _is_valid_email(captured_email):
                    session.user_email = captured_email

                session.human_mode = True
                session.human_agent_assigned = False
                await session.save()

                lead_dict = {
                    "name": session.user_name or captured_name,
                    "email": session.user_email or captured_email,
                    "phone": session.user_phone or captured_phone
                }

                try:
                    await send_lead_notification(lead_dict, session_id)
                except Exception as e:
                    logger.error(f"Failed to send human support notification for {session_id}: {str(e)}")

                await manager.forward_to_admin(
                    session_id,
                    (
                        f"HUMAN SUPPORT REQUEST [{human_payload.get('schema') or 'unknown'} v{human_payload.get('version') or '?'}]\n"
                        f"Name: {lead_dict['name']}\n"
                        f"Email: {lead_dict['email']}\n"
                        f"Phone: {lead_dict['phone']}"
                    )
                )

                confirmation = "Thanks — your details are captured. Muyiwa will contact you shortly."
                bot_msg = Message(role=MessageRole.ASSISTANT, content=confirmation)
                session.messages.append(bot_msg)
                await session.save()

                await manager.send_personal_message(confirmation, websocket)
                continue
            
            # Save User Message
            user_msg = Message(role=MessageRole.USER, content=data)
            session.messages.append(user_msg)
            await session.save()

            # 3. Check Mode: HUMAN or AI?
            if session.human_mode:
                # A. Human Mode: Forward to Admin only
                await manager.forward_to_admin(session_id, f"User: {data}")
            
            else:
                # B. AI Mode: Forward to Admin (so they can watch) AND Process
                await manager.forward_to_admin(session_id, f"User: {data}")

                # Prepare context for Groq
                history = [{"role": "system", "content": SYSTEM_PROMPT}]
                for m in session.messages:
                    history.append({"role": m.role.value, "content": m.content})

                # Call Groq
                completion = client.chat.completions.create(
                    model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
                    messages=cast(list, history),  # type: ignore
                    temperature=0.7
                )
                ai_response = completion.choices[0].message.content

                # Check for Human Transfer Request
                if ai_response and "HUMAN_TRANSFER_REQUEST:" in ai_response:
                    try:
                        transfer_reason = ai_response.split("HUMAN_TRANSFER_REQUEST:")[1].strip()
                        session.human_mode = True
                        await session.save()
                        
                        # Send notification email for human transfer
                        lead_dict = {"name": "Chat User", "email": "Transfer Request", "phone": transfer_reason}
                        await send_lead_notification(lead_dict, session_id)
                        
                        ai_response = "I'm connecting you with Muyiwa now. He'll be with you shortly! 👋"
                        logger.info(f"Human transfer requested for session {session_id}: {transfer_reason}")
                    except Exception as e:
                        logger.error(f"Human transfer error for session {session_id}: {str(e)}")
                        ai_response = "Let me connect you with Muyiwa. Please hold..."

                # Check for Lead Capture
                if ai_response and "LEAD_CAPTURED:" in ai_response:
                    try:
                        # Extract lead info from AI response
                        lead_section = ai_response.split("LEAD_CAPTURED:")[1]
                        # Simple parsing: expect format like "Name: X, Email: Y, Phone: Z"
                        lead_dict = {
                            "name": "Interested Visitor",
                            "email": "Not provided",
                            "phone": "Not provided"
                        }
                        
                        # Try to parse the extracted info
                        lines = lead_section.strip().split('\n')
                        for line in lines:
                            if 'name' in line.lower():
                                lead_dict['name'] = line.split(':', 1)[-1].strip() if ':' in line else lead_dict['name']
                            elif 'email' in line.lower():
                                lead_dict['email'] = line.split(':', 1)[-1].strip() if ':' in line else lead_dict['email']
                            elif 'phone' in line.lower():
                                lead_dict['phone'] = line.split(':', 1)[-1].strip() if ':' in line else lead_dict['phone']
                        
                        # Send Email
                        email_sent = await send_lead_notification(lead_dict, session_id)
                        if email_sent:
                            ai_response = "Thanks! I've notified Muyiwa about your interest. He might join this chat momentarily."
                            logger.info(f"Lead captured and email sent for session {session_id}: {lead_dict}")
                        else:
                            logger.warning(f"Lead captured but email failed for session {session_id}")
                            ai_response = "Thanks for your interest. Let me notify the team."
                    except Exception as e:
                        logger.error(f"Lead capture error for session {session_id}: {str(e)}")
                        ai_response = "Thanks for your interest. Let me notify the team."

                # Save & Send AI Reply
                if ai_response:
                    bot_msg = Message(role=MessageRole.ASSISTANT, content=ai_response)
                    session.messages.append(bot_msg)
                    await session.save()
                    
                    await manager.send_personal_message(ai_response, websocket)
                    await manager.forward_to_admin(session_id, f"AI: {ai_response}")

    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        manager.disconnect(session_id)
        
        
@router.websocket("/ws/admin/{session_id}")
async def admin_websocket_endpoint(websocket: WebSocket, session_id: str):
    # Security: Check authorization token (legacy static token or signed login token)
    auth_token = websocket.query_params.get("token")
    logger.info(f"🔌 Admin WebSocket connection attempt for session {session_id}")
    logger.info(f"🔌 DEBUG: auth_token received: {bool(auth_token)}, token length: {len(auth_token or '')}")
    if auth_token:
        logger.info(f"🔌 DEBUG: token (first 10 chars): {auth_token[:10]}...")
    
    admin_user = await get_admin_from_token_value(auth_token or "")
    logger.info(f"🔌 DEBUG: admin_user found: {bool(admin_user)}")
    
    if not admin_user:
        logger.warning(f"❌ Unauthorized admin access attempt for session {session_id}")
        logger.warning(f"❌ DEBUG: Token validation failed for token: {auth_token[:20] if auth_token else 'None'}...")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    logger.info(f"✅ Admin {admin_user.username} authorized for session {session_id}")
    
    await manager.connect(websocket, session_id, is_admin=True)
    
    # Notify Admin they are connected
    await websocket.send_text("--- Connected to Session ---")
    
    # Turn on Human Mode
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if session:
        session.human_mode = True
        await session.save()
        await websocket.send_text("--- HUMAN MODE ACTIVATED. AI SILENCED. ---")

    try:
        while True:
            # You type a message
            raw_data = await websocket.receive_text()
            payload = _extract_json_payload(raw_data)

            if payload and payload.get("type") == "ping":
                await manager.send_personal_message(
                    json.dumps({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}),
                    websocket
                )
                continue

            if payload and payload.get("type") == "audio":
                audio_base64 = str(payload.get("audio_base64") or "").strip()
                if not audio_base64:
                    continue

                audio_payload = {
                    "type": "audio",
                    "role": "admin",
                    "audio_base64": audio_base64,
                    "mime_type": payload.get("mime_type") or "audio/webm",
                    "duration_seconds": payload.get("duration_seconds"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }

                admin_msg = Message(role=MessageRole.ASSISTANT, content=json.dumps(audio_payload))
                if session:
                    session.messages.append(admin_msg)
                    await session.save()

                await manager.forward_to_user(session_id, json.dumps(audio_payload))
                continue

            if payload and payload.get("type") == "message":
                data = str(payload.get("content") or "").strip()
            else:
                data = raw_data

            if not data.strip():
                continue
            
            # Save it
            admin_msg = Message(role=MessageRole.ASSISTANT, content=data)
            if session:
                session.messages.append(admin_msg)
                await session.save()

            # Send to User
            await manager.forward_to_user(
                session_id,
                json.dumps({
                    "type": "message",
                    "role": "admin",
                    "content": data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            )

    except WebSocketDisconnect:
        manager.disconnect(session_id, is_admin=True)
        if session:
            session.human_mode = False
            await session.save()
    except Exception as e:
        logger.error(f"Admin WebSocket error for session {session_id}: {str(e)}")
        manager.disconnect(session_id, is_admin=True)