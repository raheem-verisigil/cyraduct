"""Public partner-reachout intake and its admin operations.

The visitor-facing POST persists the request first, then delivers the email
notification in the background (a slow or failing provider never delays or
fails the visitor). Records, delivery health, a test email and a retry for
unsent leads are available only with the full admin key.
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, Request

from .. import partner_notification, storage
from ..auth import require_full_admin
from ..models import PartnerSubmission
from ..rate_limit import limiter

router = APIRouter(prefix="/api/partners", tags=["partners"])


@router.post("")
@limiter.limit("5/minute")
def create_partner_submission(request: Request, submission: PartnerSubmission,
                              background_tasks: BackgroundTasks):
    record = storage.save_partner_submission(submission)
    background_tasks.add_task(partner_notification.deliver_partner_submission, record["id"])
    return {
        "success": True,
        "message": "Partnership request received",
    }


@router.get("", include_in_schema=True)
def list_partner_requests(limit: int = 100, x_cyraduct_admin_key: Optional[str] = Header(None)):
    require_full_admin(x_cyraduct_admin_key)
    return {"items": storage.list_partner_submissions(limit)}


@router.get("/notifications")
def notification_health(x_cyraduct_admin_key: Optional[str] = Header(None)):
    require_full_admin(x_cyraduct_admin_key)
    items = storage.list_partner_submissions(500)
    counts: dict[str, int] = {}
    for item in items:
        key = item.get("notification_status") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return {
        "provider": "resend",
        "configured": partner_notification.is_configured(),
        "notify_to": partner_notification.notification_to(),
        "from": partner_notification.notification_from(),
        "recent_lead_status_counts": counts,
    }


@router.post("/notifications/test")
@limiter.limit("5/minute")
def send_test_notification(request: Request, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Send one real email to the notification inbox so delivery can be confirmed
    end to end (API key, verified sending domain, mailbox)."""
    require_full_admin(x_cyraduct_admin_key)
    status, error = partner_notification.send_email(
        "Cyraduct test notification",
        "This is a test message from the Cyraduct API. If you can read it, partner "
        "requests and alerts will reach this inbox.",
    )
    storage.append_audit("notification_test", {"status": status, "error": error})
    return {"status": status, "error": error, "notify_to": partner_notification.notification_to()}


@router.post("/retry-notifications")
@limiter.limit("6/minute")
def retry_partner_notifications(request: Request, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Re-send notifications for leads that were never delivered (pending or
    failed). Oldest first, at most 10 per call."""
    require_full_admin(x_cyraduct_admin_key)
    unsent = [p for p in reversed(storage.list_partner_submissions(500))
              if p.get("notification_status") in partner_notification.RETRYABLE][:10]
    results: dict[str, int] = {}
    for lead in unsent:
        status = partner_notification.deliver_partner_submission(lead["id"])
        results[status] = results.get(status, 0) + 1
    storage.append_audit("partner_notifications_retried", {"attempted": len(unsent), "results": results})
    return {"attempted": len(unsent), "results": results}
