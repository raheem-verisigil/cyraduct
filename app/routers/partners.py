"""Public partner-reachout intake.

This endpoint persists a partnership request, attempts provider-backed
notification, and exposes records only through a full-admin route.
"""
from fastapi import APIRouter, Request, Header
from typing import Optional
from .. import storage
from ..models import PartnerSubmission
from ..partner_notification import notify_partner_submission
from ..rate_limit import limiter
from ..auth import require_full_admin

router = APIRouter(prefix="/api/partners", tags=["partners"])


@router.post("")
@limiter.limit("5/minute")
def create_partner_submission(request: Request, submission: PartnerSubmission):
    record = storage.save_partner_submission(submission)
    sent, error = notify_partner_submission(record)
    storage.update_partner_notification(record["id"], "sent" if sent else "pending", error)
    return {
        "success": True,
        "message": "Partnership request received",
    }


@router.get("", include_in_schema=True)
def list_partner_requests(limit: int = 100, x_cyraduct_admin_key: Optional[str] = Header(None)):
    require_full_admin(x_cyraduct_admin_key)
    return {"items": storage.list_partner_submissions(limit)}
