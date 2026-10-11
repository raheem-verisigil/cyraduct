"""Partner submission notification adapter (email via Resend).

Submissions are persisted BEFORE any notification is attempted, delivery runs in
the background so a slow provider never delays the visitor, and every outcome is
recorded on the lead so nothing is silently lost:

  sent     delivered to the Resend API
  pending  not sent yet because the provider is not configured
  failed   the provider or network call failed (error kept, truncated)

Unsent leads are visible and retryable through the full-admin API.

Mail goes ONLY to the fixed internal address (PARTNER_NOTIFICATION_TO, default
hello@cyraduct.com), never to the visitor, so the form cannot be used as a spam
relay. The visitor's address is set as Reply-To only after strict single-address
validation, so replying to the notification answers the visitor directly. Visitor
text is untrusted: it appears in the body, and only a sanitised, truncated form
of it appears in the subject.

Railway blocks outbound SMTP on Free/Trial/Hobby plans, so this uses an HTTPS
API. Configure RESEND_API_KEY and PARTNER_NOTIFICATION_FROM (an address on a
domain verified in Resend).
"""
import logging
import os
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
RETRYABLE = ("pending", "failed")
_SINGLE_ADDRESS = re.compile(r"^[^\s@<>\",;]+@[^\s@<>\",;]+\.[^\s@<>\",;]+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")


def notification_to() -> str:
    return os.getenv("PARTNER_NOTIFICATION_TO", "").strip() or "hello@cyraduct.com"


def notification_from() -> Optional[str]:
    return os.getenv("PARTNER_NOTIFICATION_FROM", "").strip() or None


def is_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY", "").strip() and notification_from())


def clean_line(value: Any, limit: int = 150) -> str:
    """Single-line, control-character-free, truncated text for headers/subjects."""
    text = " ".join(_CONTROL.sub(" ", str(value or "")).split())
    return text[:limit]


def send_email(subject: str, body: str, reply_to: Optional[str] = None) -> tuple[str, Optional[str]]:
    """Returns (status, error). Never raises and never logs secrets or message bodies."""
    if not is_configured():
        logger.warning("Notification not sent: Resend credentials are not configured")
        return "pending", "notification_provider_not_configured"
    payload: dict[str, Any] = {
        "from": notification_from(), "to": [notification_to()],
        "subject": clean_line(subject), "text": body,
    }
    if reply_to and _SINGLE_ADDRESS.match(reply_to):
        payload["reply_to"] = [reply_to]
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {os.getenv('RESEND_API_KEY', '').strip()}",
                     "Content-Type": "application/json"},
            json=payload, timeout=10.0,
        )
        response.raise_for_status()
        return "sent", None
    except Exception as exc:  # delivery must never break the caller
        logger.warning("Notification delivery failed: %s", type(exc).__name__)
        return "failed", f"notification_provider_error:{type(exc).__name__}"


def format_partner_email(record: dict[str, Any]) -> tuple[str, str, Optional[str]]:
    subject = (f"New Cyraduct partner request — {clean_line(record.get('partner_type'), 60)}"
               f" ({clean_line(record.get('company'), 80)})")
    body = "\n".join([
        "A new Cyraduct website partner request was submitted.",
        f"Name: {record['name']}",
        f"Company: {record['company']}",
        f"Email: {record['email']}",
        f"Role: {record.get('role') or 'Not provided'}",
        f"Partner type: {record['partner_type']}",
        f"Received: {record.get('created_at') or '-'}",
        f"UTM source/campaign/content: {record.get('utm_source') or '-'} / "
        f"{record.get('utm_campaign') or '-'} / {record.get('utm_content') or '-'}",
        f"Landing path: {record.get('landing_path') or '-'}",
        "",
        "Message:",
        record["message"],
        "",
        "--",
        f"Request id: {record.get('id')}",
        "Reply to this email to answer the sender. The content above was typed by an",
        "anonymous visitor: treat links and attachments with care.",
    ])
    return subject, body, record.get("email")


def notify_partner_submission(submission: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Send the notification for one submission. Returns (sent, error)."""
    status, error = send_email(*format_partner_email(submission))
    return status == "sent", error


def deliver_partner_submission(partner_id: str) -> str:
    """Load a stored lead, attempt delivery, record the outcome, return the status."""
    from . import storage  # local import: storage must not depend on notifications
    record = storage.get_partner_submission(partner_id)
    if not record:
        return "missing"
    status, error = send_email(*format_partner_email(record))
    storage.update_partner_notification(partner_id, status, error)
    return status


def notify_admin_event(subject: str, body: str) -> str:
    status, _ = send_email(f"[Cyraduct ALERT] {clean_line(subject, 120)}", body)
    return status
