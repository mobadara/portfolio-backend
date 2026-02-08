from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import SecretStr
from typing import Dict, Any, Optional
import os
import logging

logger = logging.getLogger(__name__)


def _get_mail_config() -> Optional[ConnectionConfig]:
    """Lazily initialize mail config only if required env vars are set"""
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    
    # Return None if email config is not set up
    if not mail_username or not mail_password:
        logger.warning("Email configuration not set (MAIL_USERNAME and MAIL_PASSWORD required)")
        return None
    
    try:
        return ConnectionConfig(
            MAIL_USERNAME=mail_username,
            MAIL_PASSWORD=SecretStr(mail_password),
            MAIL_FROM=mail_username,
            MAIL_PORT=int(os.getenv('MAIL_PORT', '587')),
            MAIL_SERVER=os.getenv('MAIL_SERVER', "smtp.gmail.com"),
            MAIL_STARTTLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
            MAIL_SSL_TLS=os.getenv('MAIL_USE_SSL', 'False') == 'True',
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True
        )
    except Exception as e:
        logger.error(f"Failed to initialize email config: {str(e)}")
        return None


async def send_lead_notification(lead_data: Dict[str, Any], session_id: str) -> bool:
    """Sends an email with a link to join the chat

    Args:
        lead_data (Dict[str, Any]): The lead information to be sent in the email body.
        session_id (str): The session ID of the chat session for reference in the email subject.
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Get config lazily
    conf = _get_mail_config()
    if not conf:
        logger.error(f"Email config not available for session {session_id}")
        return False
    
    try:
        admin_link = f'http://localhost:8000/admin/chat_sessions/{session_id}'
        
        # Validate required fields
        name = lead_data.get('name', 'Guest User')
        email = lead_data.get('email', 'Not provided')
        phone = lead_data.get('phone', 'Not provided')
        
        html = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #001f3f; color: white; padding: 20px; border-radius: 5px; }}
                    .content {{ margin: 20px 0; }}
                    .button {{ display: inline-block; padding: 10px 20px; background: #001f3f; color: white; text-decoration: none; border-radius: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>🚀 New Portfolio Lead Captured!</h2>
                    </div>
                    <div class="content">
                        <p><b>Name:</b> {name}</p>
                        <p><b>Email:</b> {email}</p>
                        <p><b>Phone:</b> {phone}</p>
                        <br>
                        <p>The user is currently online. Click below to take over the chat:</p>
                        <a href="{admin_link}" class="button">Join Live Chat</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
        mail_username = os.getenv('MAIL_USERNAME', '')
        message = MessageSchema(
            subject=f"Live chat request from chat session {session_id}",
            recipients=[mail_username],  # type: ignore
            body=html,
            subtype=MessageType.html
        )
        
        fm = FastMail(conf)
        await fm.send_message(message)
        logger.info(f"Lead notification sent for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send lead notification for session {session_id}: {str(e)}")
        return False
        
    except Exception as e:
        logger.error(f"Failed to send lead notification for session {session_id}: {str(e)}")
        return False