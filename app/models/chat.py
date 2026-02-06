from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field, ConfigDict

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    
class ChatSession(Document):
    session_id: str
    messages: List[Message] = Field(default_factory=list)
    
    # Lead Info: Optional fields for lead information
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
    
    # State Management
    is_active: bool = Field(default=True)
    human_agent_assigned: bool = Field(default=False) # Indicates if a human agent has been assigned to the chat session
    
    class Settings:
        name = 'chat_sessions'
        
    model_config = ConfigDict(
        json_schema_extra = {
            'example': {
                'session_id': 'abc123',
                'messages': [
                    {
                        'role': 'user',
                        'content': 'Hello, how are you?',
                        'timestamp': '2024-01-01T12:00:00'
                    },
                    {
                        'role': 'assistant',
                        'content': 'I am fine, thank you!',
                        'timestamp': '2024-01-01T12:01:00'
                    }
                ]
            }
        })