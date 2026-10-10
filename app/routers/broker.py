# Tier 3 — Broker-Enforced.
# Runtime authorizations reuse the existing signed Receipt.
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request

from ..runtime import RuntimeActionRequest
from .. import receipts, storage, url_safety
from ..indepora import IndeporaVerificationError, verify_and_bind
from ..rate_limit import limiter

router = APIRouter(prefix="/v1/broker", tags=["broker"])


@router.post("/execute")
@limiter.limit("20/minute")
async def execute(
    request: Request,
    req: RuntimeActionRequest,
    receipt_id: str,
    execution_webhook: str,
):
    kill = storage.get_kill_switch()
    if kill["active"]:
        storage.append_audit(
            "broker_blocked_kill_switch",
            {"agent_id": req.agent_id, "receipt_id": receipt_id, "reason": kill["reason"]},
        )
        raise HTTPException(
            status_code=503,
            detail=f"Cyraduct kill switch is active: {kill['reason']}",
        )

    receipt = storage.get_receipt(receipt_id)
    if not receipt:
        storage.append_audit(
            "broker_blocked_receipt_not_found",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {"executed": False, "reason": "receipt_not_found", "receipt_id": receipt_id}

    if receipt.revoked:
        storage.append_audit(
            "broker_blocked_receipt_revoked",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {"executed": False, "reason": "receipt_revoked", "receipt": receipt.model_dump()}

    if not receipts.verify_signature(receipt):
        storage.append_audit(
            "broker_blocked_signature_invalid",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {"executed": False, "reason": "signature_invalid", "receipt": receipt.model_dump()}

    if receipts.is_expired(receipt):
        storage.append_audit(
            "broker_blocked_receipt_expired",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {"executed": False, "reason": "receipt_expired", "receipt": receipt.model_dump()}

    # Re-derive the assurance binding at execution time. A receipt that was
    # issued from a verified INDEPORA record must not be reusable with a
    # caller-supplied or altered assurance object.
    if receipt.evidence_assurance is not None:
        if req.indepora_record is None:
            return {"executed": False, "reason": "indepora_record_required", "receipt": receipt.model_dump()}
        try:
            req.evidence_assurance = verify_and_bind(req.indepora_record)
        except IndeporaVerificationError as exc:
            return {"executed": False, "reason": str(exc), "receipt": receipt.model_dump()}

    if receipt.authorization_type == "runtime":
        if receipt.runtime_decision != "allow":
            storage.append_audit(
                "broker_blocked_runtime_non_allow",
                {"agent_id": req.agent_id, "receipt_id": receipt_id},
            )
            return {
                "executed": False,
                "reason": "runtime_authorization_not_allow",
                "receipt": receipt.model_dump(),
            }
        bound = receipts.verify_runtime_binding(receipt, req)
        binding_reason = "runtime_binding_mismatch"
    else:
        bound = receipts.verify_action_binding(receipt, req)
        binding_reason = "action_binding_mismatch"

    if not bound:
        storage.append_audit(
            "broker_blocked_action_mismatch",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
                "action_type": req.action_type,
                "authorization_type": receipt.authorization_type,
            },
        )
        return {
            "executed": False,
            "reason": binding_reason,
            "receipt": receipt.model_dump(),
        }

    if receipt.decision == "conditional":
        storage.append_audit(
            "broker_blocked_conditional_requires_human",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {
            "executed": False,
            "reason": "conditional_receipt_requires_human_approval",
            "receipt": receipt.model_dump(),
        }

    is_safe, webhook_reason = url_safety.validate_webhook_url(execution_webhook)
    if not is_safe:
        storage.append_audit(
            "broker_blocked_unsafe_webhook",
            {"agent_id": req.agent_id, "receipt_id": receipt_id, "reason": webhook_reason},
        )
        return {
            "executed": False,
            "reason": f"unsafe_execution_webhook:{webhook_reason}",
            "receipt": receipt.model_dump(),
        }

    claim_timestamp = datetime.now(timezone.utc).isoformat()
    if not storage.mark_receipt_consumed(receipt_id, claim_timestamp):
        storage.append_audit(
            "broker_blocked_receipt_already_consumed",
            {"agent_id": req.agent_id, "receipt_id": receipt_id},
        )
        return {
            "executed": False,
            "reason": "receipt_already_consumed",
            "receipt": receipt.model_dump(),
        }

    execution_result = None
    executed = False
    try:
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=False
        ) as client:
            resp = await client.post(
                execution_webhook,
                json={
                    "action_id": receipt.action_id,
                    "receipt_id": receipt.receipt_id,
                    "agent_id": req.agent_id,
                    "action_type": req.action_type,
                    "target": req.target,
                    "resource": req.resource,
                    "reversibility": req.reversibility,
                    "authority": req.authority,
                    "payload": req.payload,
                },
            )
            execution_result = {
                "status_code": resp.status_code,
                "body": resp.text[:2000],
            }
            executed = resp.status_code < 400
    except httpx.RequestError as e:
        execution_result = {"error": str(e)}
        executed = False

    receipt.consumed_at = claim_timestamp
    storage.append_audit(
        "broker_executed",
        {
            "action_id": receipt.action_id,
            "agent_id": req.agent_id,
            "receipt_id": receipt.receipt_id,
            "executed": executed,
            "authorization_type": receipt.authorization_type,
        },
    )

    return {
        "action_id": receipt.action_id,
        "decision": {
            "decision": receipt.decision,
            "policy_pack": receipt.policy.policy_pack,
            "policy_pack_version": receipt.policy.policy_pack_version,
            "matched_rules": receipt.policy.matched_rules,
            "reasons": receipt.policy.reasons,
        },
        "receipt": receipt.model_dump(),
        "executed": executed,
        "execution_result": execution_result,
    }
