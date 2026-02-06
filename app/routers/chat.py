from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from groq import Groq
import os

from ..models.chat import ChatSession, Message
from ..services.websocket_manager import manager
from ..services.email import send_lead_notification
from ..services.prompts import SYSTEM_PROMPT

router = APIRouter()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

@router.websocket("/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    
    # 1. Load or Create Session in DB
    session = await ChatSession.find_one(ChatSession.session_id == session_id)
    if not session:
        session = ChatSession(session_id=session_id)
        # Add system prompt implicitly to history context (not DB) for AI
        await session.insert()

    try:
        while True:
            # 2. Receive User Message
            data = await websocket.receive_text()
            
            # Save User Message
            user_msg = Message(role="user", content=data)
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
                    history.append({"role": m.role, "content": m.content})

                # Call Groq
                completion = client.chat.completions.create(
                    model="llama3-8b-8192", messages=history, temperature=0.7
                )
                ai_response = completion.choices[0].message.content

                # Check for Lead Capture
                if "LEAD_CAPTURED:" in ai_response:
                    # Parse info (Simplified)
                    try:
                        clean_info = ai_response.split("LEAD_CAPTURED:")[1]
                        # Send Email
                        lead_dict = {"name": "User", "email": "See Chat", "phone": "See Chat"} 
                        await send_lead_notification(lead_dict, session_id)
                        
                        # Switch to Human Mode automatically?
                        # session.human_mode = True 
                        # await session.save()
                        
                        ai_response = "Thanks! I've notified Muyiwa. He might join this chat momentarily."
                    except:
                        pass

                # Save & Send AI Reply
                bot_msg = Message(role="assistant", content=ai_response)
                session.messages.append(bot_msg)
                await session.save()
                
                await manager.send_personal_message(ai_response, websocket)
                await manager.forward_to_admin(session_id, f"AI: {ai_response}")

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        
        
@router.websocket("/ws/admin/{session_id}")
async def admin_websocket_endpoint(websocket: WebSocket, session_id: str):
    # Security: In real app, check a token here!
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
            admin_msg = Message(role="assistant", content=data) # Saved as assistant so it looks native
            if session:
                session.messages.append(admin_msg)
                await session.save()

            # Send to User
            await manager.forward_to_user(session_id, data)

    except WebSocketDisconnect:
        manager.disconnect(session_id, is_admin=True)
        # Optional: Turn AI back on when you leave?
        if session:
            session.human_mode = False
            await session.save()