from typing import List, Optional
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from enum import Enum

class MessageRole(str, Enum):
    """Valid message roles for chat"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Message(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        json_schema_extra={
            'example': {
                'role': 'user',
                'content': 'Hello, how are you?',
                'timestamp': '2024-01-01T12:00:00'
            }
        }
    )
    
class ChatSession(Document):
    session_id: str = Field(..., min_length=1, description="Unique session identifier")
    messages: List[Message] = Field(default_factory=list)
    
    # Lead Info: Optional fields for lead information
    user_name: Optional[str] = Field(None, min_length=1)
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    
    # State Management
    is_active: bool = Field(default=True)
    human_mode: bool = Field(default=False, description="Indicates if human agent is handling the conversation")
    human_agent_assigned: bool = Field(default=False, description="Indicates if a human agent has been assigned to the chat session")
    
    class Settings:
        name = 'chat_sessions'
        
    model_config = ConfigDict(
        json_schema_extra={
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
        }
    )