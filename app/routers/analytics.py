"""Privacy-conscious first-party engagement events.

Only allowlisted event names and bounded properties are accepted. The API does
not store IP addresses, form values, receipt IDs, or raw URLs.
"""
from fastapi import APIRouter, Request

from .. import storage
from ..models import AnalyticsEvent
from ..rate_limit import limiter

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.post("/events", status_code=202)
@limiter.limit("120/minute")
def record_event(request: Request, event: AnalyticsEvent):
    storage.save_analytics_event(event)
    return {"accepted": True}
