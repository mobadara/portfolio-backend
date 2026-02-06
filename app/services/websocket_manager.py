from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.admin_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str, is_admin: bool = False):
        await websocket.accept()
        if is_admin:
            self.admin_connections[session_id] = websocket
        else:
            self.active_connections[session_id] = websocket
            
    def disconnect(self, session_id: str, is_admin: bool = False):
        if is_admin:
            if session_id in self.admin_connections:
                del self.admin_connections[session_id]
        else:
            if session_id in self.active_connections:
                del self.active_connections[session_id]
                
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def forward_to_admin(self, session_id: str, message: str):
        """If admin is connected, forward user's message to them"""
        if session_id in self.admin_connections:
            await self.admin_connections[session_id].send_text(message)

    async def forward_to_user(self, session_id: str, message: str):
        """Forward admin's message to the user"""
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(message)

manager = ConnectionManager()