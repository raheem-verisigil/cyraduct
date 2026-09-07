"""
Tier 3 — Broker-Enforced.

The agent action physically routes through Cyraduct. No bypass path
exists at this layer for integrated actions. This is the strongest
guarantee tier and the highest operational-cost tier: Cyraduct's
availability and latency now sit on the critical path (documented
tradeoff — not hidden from the caller).

For this reference implementation, "executing" the action means calling
a caller-supplied webhook only after a passing policy decision. A
production broker would instead terminate provider-specific protocols
(MCP, A2A, HTTP tool calls) directly — that integration layer is a
documented roadmap item, not something this endpoint should be mistaken for.
"""
import httpx
from fastapi import APIRouter, HTTPException
from ..models import ActionRequest, new_id
from .. import policy_engine, receipts, storage

router = APIRouter(prefix="/v1/broker", tags=["broker"])


@router.post("/execute")
async def execute(req: ActionRequest, execution_webhook: str):
    kill = storage.get_kill_switch()
    if kill["active"]:
        storage.append_audit("broker_blocked_kill_switch", {"agent_id": req.agent_id, "reason": kill["reason"]})
        raise HTTPException(status_code=503, detail=f"Cyraduct kill switch is active: {kill['reason']}")

    action_id = new_id("act")
    decision = policy_engine.evaluate(req)

    if decision.decision == "deny":
        storage.append_audit("broker_denied", {
            "action_id": action_id, "agent_id": req.agent_id, "reasons": decision.reasons
        })
        return {"action_id": action_id, "decision": decision.model_dump(), "executed": False, "execution_result": None}

    prev_hash = storage.get_last_receipt_hash(req.agent_id)
    receipt = receipts.issue_receipt(
        req, action_id, decision.decision, decision.policy_pack, decision.policy_pack_version,
        decision.matched_rules, decision.reasons, prev_receipt_hash=prev_hash,
    )
    storage.save_receipt(receipt)

    execution_result = None
    executed = False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(execution_webhook, json={
                "action_id": action_id,
                "receipt_id": receipt.receipt_id,
                "agent_id": req.agent_id,
                "action_type": req.action_type,
                "payload": req.payload,
            })
            execution_result = {"status_code": resp.status_code, "body": resp.text[:2000]}
            executed = resp.status_code < 400
    except httpx.RequestError as e:
        execution_result = {"error": str(e)}
        executed = False

    storage.append_audit("broker_executed", {
        "action_id": action_id,
        "agent_id": req.agent_id,
        "receipt_id": receipt.receipt_id,
        "executed": executed,
    })

    return {
        "action_id": action_id,
        "decision": decision.model_dump(),
        "receipt": receipt.model_dump(),
        "executed": executed,
        "execution_result": execution_result,
    }
