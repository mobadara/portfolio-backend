from fastapi import WebSocket
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        self.admin_session_list_connections: List[WebSocket] = []  # For session list subscribers
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

    async def close_session_connections(self, session_id: str) -> None:
        """Close both user and admin connections for a session if open."""
        user_socket: Optional[WebSocket] = self.active_connections.get(session_id)
        admin_socket: Optional[WebSocket] = self.admin_connections.get(session_id)

        if user_socket:
            try:
                await user_socket.close(code=1000)
            except Exception as e:
                logger.warning(f"Failed closing user websocket for {session_id}: {str(e)}")

        if admin_socket:
            try:
                await admin_socket.close(code=1000)
            except Exception as e:
                logger.warning(f"Failed closing admin websocket for {session_id}: {str(e)}")

        self.disconnect(session_id)
        self.disconnect(session_id, is_admin=True)
                
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

    async def subscribe_to_session_list(self, websocket: WebSocket) -> None:
        """Subscribe admin to real-time session list updates"""
        await websocket.accept()
        self.admin_session_list_connections.append(websocket)
        logger.info(f"Admin subscribed to session list updates. Total subscribers: {len(self.admin_session_list_connections)}")

    def unsubscribe_from_session_list(self, websocket: WebSocket) -> None:
        """Unsubscribe admin from session list updates"""
        if websocket in self.admin_session_list_connections:
            self.admin_session_list_connections.remove(websocket)
            logger.info(f"Admin unsubscribed from session list updates. Total subscribers: {len(self.admin_session_list_connections)}")

    async def broadcast_session_list_update(self, update_event: str) -> None:
        """Broadcast session list update to all subscribed admins"""
        disconnected_clients = []
        for websocket in self.admin_session_list_connections:
            try:
                await websocket.send_text(update_event)
            except Exception as e:
                logger.warning(f"Failed to send session list update: {str(e)}")
                disconnected_clients.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected_clients:
            self.unsubscribe_from_session_list(websocket)

manager = ConnectionManager()