"""
Tier 1 — Advisory.

Cyraduct evaluates and returns a decision. It does NOT sit in the
execution path. Nothing here stops the action from happening if the
caller ignores the response — that is the defining, documented limit
of this tier (see non-goals).
"""
from fastapi import APIRouter
from ..models import ActionRequest, PolicyDecision, new_id
from .. import policy_engine, storage

router = APIRouter(prefix="/v1/advisory", tags=["advisory"])


@router.post("/evaluate", response_model=PolicyDecision)
def evaluate(req: ActionRequest):
    action_id = new_id("act")
    decision = policy_engine.evaluate(req)
    storage.append_audit("advisory_evaluate", {
        "action_id": action_id,
        "agent_id": req.agent_id,
        "action_type": req.action_type,
        "decision": decision.decision,
        "matched_rules": decision.matched_rules,
    })
    return decision
