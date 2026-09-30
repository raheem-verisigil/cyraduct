"""Public partner-reachout intake.

This endpoint is deliberately narrow: it accepts a partnership request,
persists it, and leaves notification delivery behind a future seam.
"""
from fastapi import APIRouter, Request
from slowapi.util import get_remote_address

from .. import storage
from ..models import PartnerSubmission
from ..partner_notification import notify_partner_submission
from ..rate_limit import limiter

router = APIRouter(prefix="/api/partners", tags=["partners"])


@router.post("")
@limiter.limit("5/minute")
def create_partner_submission(request: Request, submission: PartnerSubmission):
    record = storage.save_partner_submission(submission)
    notify_partner_submission(record)
    return {
        "success": True,
        "message": "Partnership request received",
    }
