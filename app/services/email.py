from fastapi_mail import FastMail, MessageSchema, ConnectionConfig,\
                        MessageType
from pydantic import EmailStr
from typing import List, Dict, Any
import os


conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv('MAIL_USERNAME', ''),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD', ''),
    MAIL_FROM=os.getenv('MAIL_USERNAME', ''),
    MAIL_PORT=int(os.getenv('MAIL_PORT', '587')),
    MAIL_SERVER=os.getenv('MAIL_SERVER', "smtp.gmail.com"),
    MAIL_STARTTLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
    MAIL_SSL_TLS=os.getenv('MAIL_USE_SSL', 'False') == 'True',
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_lead_notification(lead_data: Dict[str, Any], sessio_id: str):
    """Sends an email with a link to join the chat

    Args:
        lead_data (Dict[str, Any]): The lead information to be sent in the email body.
        sessio_id (str): The session ID of the chat session for reference in the email subject.
        
    Returns:
        None
    """
    admin_link = f'http://localhost:8000/admin/chat_sessions/{sessio_id}'  # Link to the admin interface for the specific chat session
    html = f"""
    <h3>🚀 New Portfolio Lead Captured!</h3>
    <p><b>Name:</b> {lead_data.get('name')}</p>
    <p><b>Email:</b> {lead_data.get('email')}</p>
    <p><b>Phone:</b> {lead_data.get('phone')}</p>
    <br>
    <p>The user is currently online. Click below to take over the chat:</p>
    <a href="{admin_link}" style="padding: 10px 20px; background: #001f3f; color: white; text-decoration: none; border-radius: 5px;">Join Live Chat</a>
    """
    message = MessageSchema(
        subject=f"Live chat request from chat session {sessio_id}",
        recipients=[os.getenv('MAIL_USERNAME', '')],
        body=html,
        subtype=MessageType.html
    )
    
    fm = FastMail(conf)
    await fm.send_message(message)