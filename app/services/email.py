from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from pydantic import SecretStr
from typing import Dict, Any, Optional
import os
import logging
import requests

logger = logging.getLogger(__name__)


def _get_mail_config() -> Optional[ConnectionConfig]:
    """Lazily initialize mail config only if required env vars are set"""
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    
    # Return None if email config is not set up
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        logger.warning("Email configuration not set (MAIL_USERNAME and MAIL_PASSWORD required)")
        return None
    
    try:
        return ConnectionConfig(
            MAIL_USERNAME=MAIL_USERNAME,
            MAIL_PASSWORD=SecretStr(MAIL_PASSWORD),
            MAIL_FROM=MAIL_USERNAME,
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


# async def send_lead_notification(lead_data: Dict[str, Any], session_id: str) -> bool:
#     """Sends an email with a link to join the chat

#     Args:
#         lead_data (Dict[str, Any]): The lead information to be sent in the email body.
#         session_id (str): The session ID of the chat session for reference in the email subject.
        
#     Returns:
#         bool: True if email was sent successfully, False otherwise
#     """
#     # Get config lazily
#     conf = _get_mail_config()
#     if not conf:
#         logger.error(f"Email config not available for session {session_id}")
#         return False
    
#     try:
#         backend_url = os.getenv('BACKEND_URL', 'https://portfolio-backend-tjq3.onrender.com')
#         admin_link = f'{backend_url}/admin/chat_sessions/{session_id}'
        
#         # Validate required fields
#         name = lead_data.get('name', 'Guest User')
#         email = lead_data.get('email', 'Not provided')
#         phone = lead_data.get('phone', 'Not provided')
        
#         html = f"""
#         <html>
#             <head>
#                 <style>
#                     body {{ font-family: Arial, sans-serif; }}
#                     .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
#                     .header {{ background-color: #001f3f; color: white; padding: 20px; border-radius: 5px; }}
#                     .content {{ margin: 20px 0; }}
#                     .button {{ display: inline-block; padding: 10px 20px; background: #001f3f; color: white; text-decoration: none; border-radius: 5px; }}
#                 </style>
#             </head>
#             <body>
#                 <div class="container">
#                     <div class="header">
#                         <h2>🚀 New Portfolio Lead Captured!</h2>
#                     </div>
#                     <div class="content">
#                         <p><b>Name:</b> {name}</p>
#                         <p><b>Email:</b> {email}</p>
#                         <p><b>Phone:</b> {phone}</p>
#                         <br>
#                         <p>The user is currently online. Click below to take over the chat:</p>
#                         <a href="{admin_link}" class="button">Join Live Chat</a>
#                     </div>
#                 </div>
#             </body>
#         </html>
#         """
        
#         mail_username = os.getenv('MAIL_USERNAME', '')
#         message = MessageSchema(
#             subject=f"Live chat request from chat session {session_id}",
#             recipients=[mail_username],  # type: ignore
#             body=html,
#             subtype=MessageType.html
#         )
        
#         fm = FastMail(conf)
#         await fm.send_message(message)
#         logger.info(f"Lead notification sent for session {session_id}")
#         return True
#     except Exception as e:
#         logger.error(f"Failed to send lead notification for session {session_id}: {str(e)}")
#         return False


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("MAIL_USERNAME")
SENDER_NAME = "Muyiwa's AI Assistant"

async def send_lead_notification(lead_data: Dict[str, Any], session_id: str):
    """
    Sends an email using Brevo HTTP API (Bypasses SMTP port blocking).
    """
    url = "https://api.brevo.com/v3/smtp/email"
    
    admin_link = f"https://portfolio-frontend-livid.vercel.app//admin/chat/{session_id}"
    
    html_content = f"""
    <html>
    <body>
        <h3>🚀 New Portfolio Lead Captured!</h3>
        <p><b>Name:</b> {lead_data.get('name', 'N/A')}</p>
        <p><b>Email:</b> {lead_data.get('email', 'N/A')}</p>
        <p><b>Phone:</b> {lead_data.get('phone', 'N/A')}</p>
        <br>
        <p>The user is currently online. Click below to take over:</p>
        <a href="{admin_link}" style="padding: 10px 20px; background: #001f3f; color: white; text-decoration: none; border-radius: 5px;">Join Live Chat</a>
    </body>
    </html>
    """

    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": SENDER_EMAIL, "name": "Muyiwa Obadara"}],
        "subject": "🔥 Hot Lead: Live Chat Request",
        "htmlContent": html_content
    }

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            logger.info("✅ Email sent successfully via Brevo!")
        else:
            logger.error(f"❌ Email failed: {response.text}")
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")