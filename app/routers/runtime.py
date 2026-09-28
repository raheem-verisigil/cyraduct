from fastapi import APIRouter, HTTPException

from app import storage
from app.runtime import RuntimeActionRequest, RuntimeDecision, evaluate

router = APIRouter(prefix="/v1/runtime", tags=["runtime"])


@router.post("/evaluate", response_model=RuntimeDecision)
def evaluate_runtime(req: RuntimeActionRequest):
    if storage.get_kill_switch()["active"]:
        storage.append_audit(
            "runtime_evaluate_blocked",
            {"agent_id": req.agent_id, "action_type": req.action_type},
        )
        raise HTTPException(status_code=503, detail="kill_switch_active")

    decision = evaluate(req)
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
        },
    )
    return decision
