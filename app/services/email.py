from typing import Dict, Any
import os
import logging
import requests
from html import escape

logger = logging.getLogger(__name__)


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("MAIL_USERNAME")
SENDER_NAME = "Muyiwa's AI Assistant"
FRONTEND_URL = (os.getenv("FRONTEND_URL") or "").rstrip("/")


def _send_html_email(subject: str, html_content: str, recipient_email: str, recipient_name: str = "") -> bool:
    if not BREVO_API_KEY:
        logger.error("❌ BREVO_API_KEY is missing; cannot send email")
        return False

    if not SENDER_EMAIL:
        logger.error("❌ MAIL_USERNAME is missing; cannot send email")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": recipient_email, "name": recipient_name or recipient_email}],
        "subject": subject,
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
            logger.info("✅ Email sent successfully via Brevo")
            return True

        logger.error(f"❌ Email failed: {response.text}")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending email: {e}")
        return False

async def send_lead_notification(lead_data: Dict[str, Any], session_id: str) -> bool:
    """
    Sends an email using Brevo HTTP API (Bypasses SMTP port blocking).
    """
    admin_link = f"{FRONTEND_URL}/admin/chat/{session_id}"
    lead_name = lead_data.get('name', 'N/A')
    lead_email = lead_data.get('email', 'N/A')
    lead_phone = lead_data.get('phone', 'N/A')
    lead_country = lead_data.get('country_code', 'N/A')
    lead_local_phone = lead_data.get('phone_local', 'N/A')
    lead_notes = lead_data.get('notes', 'N/A')

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
                                                <td style="width:120px;font-size:13px;color:#64748b;">Country</td>
                                                <td style="font-size:15px;font-weight:600;color:#0f172a;">{lead_country}</td>
                                            </tr>
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Local Phone</td>
                                                <td style="font-size:15px;font-weight:600;color:#0f172a;">{lead_local_phone}</td>
                                            </tr>
                                            <tr>
                                                <td style="width:120px;font-size:13px;color:#64748b;">Notes</td>
                                                <td style="font-size:15px;color:#334155;">{escape(lead_notes)}</td>
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

    return _send_html_email(
        subject="New Human Chat Request • Portfolio",
        html_content=html_content,
        recipient_email=SENDER_EMAIL or "",
        recipient_name="Muyiwa Obadara"
    )


async def send_session_deleted_notification(recipient_email: str, session_id: str) -> bool:
    if not recipient_email:
        return False

    safe_session = escape(session_id)
    html_content = f"""
        <html>
            <body style=\"margin:0;padding:0;background:#f2f5fb;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;\">
                <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"padding:28px 12px;\">
                    <tr>
                        <td align=\"center\">
                            <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:620px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #dbe3f0;box-shadow:0 12px 32px rgba(15,23,42,0.08);\">
                                <tr>
                                    <td style=\"padding:22px 24px;background:linear-gradient(135deg,#001f3f 0%,#003a73 100%);color:#ffffff;\">
                                        <div style=\"font-size:12px;letter-spacing:1px;text-transform:uppercase;opacity:0.9;\">Portfolio Live Chat</div>
                                        <h2 style=\"margin:8px 0 0;font-size:22px;line-height:1.3;\">Your Chat Session Was Closed</h2>
                                    </td>
                                </tr>
                                <tr>
                                    <td style=\"padding:22px 24px;\">
                                        <p style=\"margin:0 0 14px;font-size:15px;line-height:1.6;color:#334155;\">
                                            A live-support session has been removed by the admin team.
                                        </p>
                                        <p style=\"margin:0 0 14px;font-size:15px;line-height:1.6;color:#334155;\">
                                            Session ID: <strong style=\"font-family:ui-monospace,SFMono-Regular,Menlo,monospace;\">{safe_session}</strong>
                                        </p>
                                        <p style=\"margin:0;font-size:14px;line-height:1.6;color:#64748b;\">
                                            If you open the website chat again, a new session will start automatically.
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

    return _send_html_email(
        subject="Your Portfolio Chat Session Was Closed",
        html_content=html_content,
        recipient_email=recipient_email,
        recipient_name=recipient_email
    )