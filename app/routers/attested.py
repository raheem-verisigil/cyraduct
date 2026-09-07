"""
Tier 2 — Attested.

Cyraduct is not in the execution path, but a compliant sink MUST call
/verify and refuse to act without a valid, unexpired, unrevoked receipt.
This is the recommended default tier for most consequential-action
deployments (see positioning language).
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from ..models import ActionRequest, VerifyResult, new_id
from .. import policy_engine, receipts, storage
from ..config import ADMIN_API_KEY

router = APIRouter(prefix="/v1/attested", tags=["attested"])


@router.post("/evaluate")
def evaluate(req: ActionRequest):
    kill = storage.get_kill_switch()
    if kill["active"]:
        storage.append_audit("attested_blocked_kill_switch", {"agent_id": req.agent_id, "reason": kill["reason"]})
        raise HTTPException(status_code=503, detail=f"Cyraduct kill switch is active: {kill['reason']}")

    action_id = new_id("act")
    decision = policy_engine.evaluate(req)

    result = {"action_id": action_id, "decision": decision.model_dump(), "receipt": None}

    if decision.decision in ("allow", "conditional"):
        prev_hash = storage.get_last_receipt_hash(req.agent_id)
        receipt = receipts.issue_receipt(
            req, action_id, decision.decision, decision.policy_pack, decision.policy_pack_version,
            decision.matched_rules, decision.reasons, prev_receipt_hash=prev_hash,
        )
        storage.save_receipt(receipt)
        result["receipt"] = receipt.model_dump()

    storage.append_audit("attested_evaluate", {
        "action_id": action_id,
        "agent_id": req.agent_id,
        "action_type": req.action_type,
        "decision": decision.decision,
        "receipt_id": result["receipt"]["receipt_id"] if result["receipt"] else None,
    })
    return result


@router.get("/verify/{receipt_id}", response_model=VerifyResult)
def verify(receipt_id: str):
    """Called by the sink (bank API, infra control plane, EHR, etc.) before
    it executes the action. This is the actual enforcement point in Tier 2.
    Verification uses this instance's own key by default; an external,
    independent verifier should instead fetch /v1/public-key and check the
    signature itself (see verify_receipt.py)."""
    receipt = storage.get_receipt(receipt_id)
    if not receipt:
        return VerifyResult(valid=False, reason="receipt_not_found")
    if receipt.revoked:
        return VerifyResult(valid=False, reason="receipt_revoked", receipt=receipt)
    if not receipts.verify_signature(receipt):
        return VerifyResult(valid=False, reason="signature_invalid", receipt=receipt)
    if receipts.is_expired(receipt):
        return VerifyResult(valid=False, reason="receipt_expired", receipt=receipt)

    storage.append_audit("receipt_verified", {"receipt_id": receipt_id})
    return VerifyResult(valid=True, reason="ok", receipt=receipt)


@router.post("/revoke/{receipt_id}")
def revoke(receipt_id: str, x_cyraduct_admin_key: Optional[str] = Header(None)):
    if x_cyraduct_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    ok = storage.revoke_receipt(receipt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Receipt not found")
    storage.append_audit("receipt_revoked", {"receipt_id": receipt_id, "scope": "single"})
    return {"receipt_id": receipt_id, "revoked": True}


@router.post("/revoke-agent/{agent_id}")
def revoke_agent(agent_id: str, reason: Optional[str] = None, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Fleet/agent-scoped revocation: invalidate every currently-active
    receipt this agent holds. This is the 'kill this agent now' operation —
    a sink checking /verify on any of that agent's receipts will see them
    as revoked immediately."""
    if x_cyraduct_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    count = storage.revoke_by_agent(agent_id)
    storage.append_audit("receipt_revoked", {"agent_id": agent_id, "scope": "agent", "count": count, "reason": reason})
    return {"agent_id": agent_id, "revoked_count": count, "reason": reason}
