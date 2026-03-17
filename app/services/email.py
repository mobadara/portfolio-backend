from typing import Dict, Any
import os
import logging
import requests

logger = logging.getLogger(__name__)


# def _get_mail_config() -> Optional[ConnectionConfig]:
#     """Lazily initialize mail config only if required env vars are set"""
#     MAIL_USERNAME = os.getenv('MAIL_USERNAME')
#     MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    
#     # Return None if email config is not set up
#     if not MAIL_USERNAME or not MAIL_PASSWORD:
#         logger.warning("Email configuration not set (MAIL_USERNAME and MAIL_PASSWORD required)")
#         return None
    
#     try:
#         return ConnectionConfig(
#             MAIL_USERNAME=MAIL_USERNAME,
#             MAIL_PASSWORD=SecretStr(MAIL_PASSWORD),
#             MAIL_FROM=MAIL_USERNAME,
#             MAIL_PORT=int(os.getenv('MAIL_PORT', '587')),
#             MAIL_SERVER=os.getenv('MAIL_SERVER', "smtp.gmail.com"),
#             MAIL_STARTTLS=os.getenv('MAIL_USE_TLS', 'True') == 'True',
#             MAIL_SSL_TLS=os.getenv('MAIL_USE_SSL', 'False') == 'True',
#             USE_CREDENTIALS=True,
#             VALIDATE_CERTS=True
#         )
#     except Exception as e:
#         logger.error(f"Failed to initialize email config: {str(e)}")
#         return None


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
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://portfolio-frontend-livid.vercel.app").rstrip("/")

async def send_lead_notification(lead_data: Dict[str, Any], session_id: str) -> bool:
    """
    Sends an email using Brevo HTTP API (Bypasses SMTP port blocking).
    """
    if not BREVO_API_KEY:
        logger.error("❌ BREVO_API_KEY is missing; cannot send lead notification")
        return False

    if not SENDER_EMAIL:
        logger.error("❌ MAIL_USERNAME is missing; cannot send lead notification")
        return False

    url = "https://api.brevo.com/v3/smtp/email"

    admin_link = f"{FRONTEND_URL}/admin/chat/{session_id}"
    lead_name = lead_data.get('name', 'N/A')
    lead_email = lead_data.get('email', 'N/A')
    lead_phone = lead_data.get('phone', 'N/A')

    html_content = f"""
        <html>
            <body style="margin:0;padding:0;background:#f2f5fb;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:28px 12px;">
                    <tr>
                        <td align="center">
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #dbe3f0;box-shadow:0 12px 32px rgba(15,23,42,0.08);">
                                <tr>
                                    <td style="padding:22px 24px;background:linear-gradient(135deg,#001f3f 0%,#003a73 100%);color:#ffffff;">
                                        <div style="font-size:12px;letter-spacing:1px;text-transform:uppercase;opacity:0.9;">Portfolio Live Chat</div>
                                        <h2 style="margin:8px 0 0;font-size:22px;line-height:1.3;">New Human Support Request</h2>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding:22px 24px 8px;">
                                        <p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:#334155;">
                                            A visitor requested to speak with you. Use the button below to open the admin chat and join this session.
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding:0 24px 8px;">
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:separate;border-spacing:0 10px;">
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Name</td>
                                                <td style="font-size:15px;font-weight:600;color:#0f172a;">{lead_name}</td>
                                            </tr>
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Email</td>
                                                <td style="font-size:15px;font-weight:600;color:#0f172a;">{lead_email}</td>
                                            </tr>
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Phone</td>
                                                <td style="font-size:15px;font-weight:600;color:#0f172a;">{lead_phone}</td>
                                            </tr>
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Session ID</td>
                                                <td style="font-size:13px;color:#334155;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{session_id}</td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding:18px 24px 28px;">
                                        <a href="{admin_link}" style="display:inline-block;padding:12px 18px;border-radius:10px;background:#0b63f6;color:#ffffff;text-decoration:none;font-weight:700;font-size:14px;">Open Admin Chat</a>
                                        <p style="margin:12px 0 0;font-size:12px;color:#64748b;line-height:1.5;">
                                            If the button does not work, copy this URL:<br />
                                            <span style="color:#334155;word-break:break-all;">{admin_link}</span>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
            </body>
        </html>
    """

    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": SENDER_EMAIL, "name": "Muyiwa Obadara"}],
        "subject": "New Human Chat Request • Portfolio",
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
            return True
        else:
            logger.error(f"❌ Email failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")
        return False