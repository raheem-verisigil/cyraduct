from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app import auth, config, receipts, storage
from app.rate_limit import limiter
from app.runtime import RuntimeActionRequest, RuntimeDecision, evaluate

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/evaluate", response_model=RuntimeDecision)
@limiter.limit("60/minute")
def evaluate_runtime(
    request: Request,
    req: RuntimeActionRequest,
    x_cyraduct_runtime_key: Optional[str] = Header(None),
):
    auth.require_service_key(
        x_cyraduct_runtime_key,
        config.RUNTIME_API_KEY,
        "CYRADUCT_RUNTIME_API_KEY",
    )

    if storage.get_kill_switch()["active"]:
        storage.append_audit(
            "runtime_evaluate_blocked",
            {"agent_id": req.agent_id, "action_type": req.action_type},
        )
        raise HTTPException(status_code=503, detail="kill_switch_active")

    decision = evaluate(req)

    if decision.decision == "allow":
        prev_hash = storage.get_last_receipt_hash(req.agent_id)
        authorization = receipts.issue_runtime_receipt(
            req, decision, prev_receipt_hash=prev_hash
        )
        storage.save_receipt(authorization)
        decision.authorization = authorization

    storage.append_audit(
        "runtime_evaluate",
        {
            "event_id": decision.action_id,
            "agent_id": req.agent_id,
            "action_id": decision.action_id,
            "action_type": req.action_type,
            "consequence_class": req.consequence_class,
            "decision": decision.decision,
            "reasons": decision.reasons,
            "signals": decision.signals,
            "authorization_id": (
                decision.authorization.receipt_id
                if decision.authorization
                else None
            ),
        },
    )
    return decision
