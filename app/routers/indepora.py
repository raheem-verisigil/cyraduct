"""INDEPORA partnership adapter endpoints."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from ..indepora import IndeporaVerificationError, verify_and_bind
from ..rate_limit import limiter

router = APIRouter(prefix="/v1/indepora", tags=["indepora"])


@router.post("/verify")
@limiter.limit("30/minute")
def verify_continuity_record(request: Request, record: Dict[str, Any]):
    """Verify a signed INDEPORA Continuity Record.

    The response is intentionally limited to allowlisted facts that Cyraduct
    can bind into an action envelope. It does not decide whether the evidence
    is true or whether a business action should be authorized.
    """
    try:
        binding = verify_and_bind(record)
    except IndeporaVerificationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"valid": True, "binding": binding.model_dump(by_alias=True)}
