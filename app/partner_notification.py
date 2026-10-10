"""Partner submission notification adapter.

Submissions are persisted before notification is attempted. Resend is optional
until its API key and verified sender are configured in the deployment.
"""
import os
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)
NOTIFICATION_TO = os.getenv("PARTNER_NOTIFICATION_TO", "hello@cyraduct.com")
RESEND_URL = "https://api.resend.com/emails"


def notify_partner_submission(submission: dict[str, Any]) -> tuple[bool, str | None]:
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("PARTNER_NOTIFICATION_FROM")
    if not api_key or not sender:
        logger.warning("Partner notification not sent: Resend credentials are not configured")
        return False, "notification_provider_not_configured"

    subject = f"New Cyraduct partner request — {submission['partner_type']}"
    text = "\n".join([
        "A new Cyraduct website partner request was submitted.",
        f"Name: {submission['name']}",
        f"Company: {submission['company']}",
        f"Email: {submission['email']}",
        f"Role: {submission.get('role') or 'Not provided'}",
        f"Partner type: {submission['partner_type']}",
        f"UTM source/campaign/content: {submission.get('utm_source') or '-'} / {submission.get('utm_campaign') or '-'} / {submission.get('utm_content') or '-'}",
        f"Landing path: {submission.get('landing_path') or '-'}",
        "",
        "Message:",
        submission["message"],
    ])
    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"from": sender, "to": [NOTIFICATION_TO], "subject": subject, "text": text},
            timeout=10.0,
        )
        response.raise_for_status()
        return True, None
    except httpx.HTTPError as exc:
        logger.exception("Partner notification failed")
        return False, f"notification_provider_error:{type(exc).__name__}"
