from fastapi import WebSocket
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str, is_admin: bool = False) -> None:
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        if is_admin:
            self.admin_connections[session_id] = websocket
            logger.info(f"Admin connected to session {session_id}")
        else:
            self.active_connections[session_id] = websocket
            logger.info(f"User connected to session {session_id}")
            
    def disconnect(self, session_id: str, is_admin: bool = False) -> None:
        """Remove WebSocket connection"""
        if is_admin:
            if session_id in self.admin_connections:
                del self.admin_connections[session_id]
                logger.info(f"Admin disconnected from session {session_id}")
        else:
            if session_id in self.active_connections:
                del self.active_connections[session_id]
                logger.info(f"User disconnected from session {session_id}")
                
    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {str(e)}")

    async def forward_to_admin(self, session_id: str, message: str) -> None:
        """If admin is connected, forward user's message to them"""
        if session_id in self.admin_connections:
            try:
                await self.admin_connections[session_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to forward message to admin for session {session_id}: {str(e)}")

    async def forward_to_user(self, session_id: str, message: str) -> None:
        """Forward admin's message to the user"""
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to forward message to user for session {session_id}: {str(e)}")

manager = ConnectionManager()