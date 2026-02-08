from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from groq import Groq
from typing import cast, Optional
import os
import logging

from ..models.chat import ChatSession, Message, MessageRole
from ..services.websocket_manager import manager
from ..services.email import send_lead_notification
from ..services.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter()


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
async def get_admin_chat_session(session_id: str):
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        return {"status": "not_found", "session_id": session_id}

    admin_ws_base = os.getenv("ADMIN_WS_BASE", "wss://portfolio-backend-6t3l.onrender.com")
    admin_ws_url = f"{admin_ws_base}/ws/admin/{session_id}"

    return {
        "status": "ok",
        "session_id": session_id,
        "human_mode": session.human_mode,
        "messages": session.model_dump().get("messages", []),
        "admin_websocket": {
            "url": admin_ws_url,
            "token_required": True,
            "token_env": "ADMIN_AUTH_TOKEN"
        }
    }


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
            data = await websocket.receive_text()
            
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
    # Security: Check authorization token
    auth_token = websocket.query_params.get("token")
    if not auth_token or auth_token != os.getenv("ADMIN_AUTH_TOKEN", ""):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        logger.warning(f"Unauthorized admin access attempt for session {session_id}")
        return
    
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
            data = await websocket.receive_text()
            
            # Save it
            admin_msg = Message(role=MessageRole.ASSISTANT, content=data)
            if session:
                session.messages.append(admin_msg)
                await session.save()

            # Send to User
            await manager.forward_to_user(session_id, data)

    except WebSocketDisconnect:
        manager.disconnect(session_id, is_admin=True)
        if session:
            session.human_mode = False
            await session.save()
    except Exception as e:
        logger.error(f"Admin WebSocket error for session {session_id}: {str(e)}")
        manager.disconnect(session_id, is_admin=True)