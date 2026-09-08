"""
Tier 3 — Broker-Enforced.

An integrated action must present a valid Cyraduct receipt before execution.

Enforcement invariant:

    presented receipt
        -> exists
        -> not revoked
        -> signature valid
        -> not expired
        -> action/agent binding valid
        -> execution webhook destination is safe (SSRF check)
        -> execution webhook

Any failed check blocks execution before the webhook is called.

This reference implementation uses a caller-supplied webhook as the execution
sink. A production broker may terminate provider-specific protocols directly
(MCP, A2A, HTTP tool calls, etc.).

SSRF note: execution_webhook is caller-supplied, so it is validated via
url_safety.validate_webhook_url() before any request is made, and the
HTTP client below disables redirect-following — a URL that passes
validation could otherwise redirect to an internal address at request
time. See app/url_safety.py for the full threat model and residual risk.
"""

import httpx
from fastapi import APIRouter, HTTPException

from ..models import ActionRequest
from .. import receipts, storage, url_safety


router = APIRouter(prefix="/v1/broker", tags=["broker"])


@router.post("/execute")
async def execute(
    req: ActionRequest,
    receipt_id: str,
    execution_webhook: str,
):
    # 1. Global emergency stop must always take precedence.
    kill = storage.get_kill_switch()
    if kill["active"]:
        storage.append_audit(
            "broker_blocked_kill_switch",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
                "reason": kill["reason"],
            },
        )
        raise HTTPException(
            status_code=503,
            detail=f"Cyraduct kill switch is active: {kill['reason']}",
        )

    # 2. The broker does NOT create a new authorization receipt.
    #    The caller must present an existing receipt.
    receipt = storage.get_receipt(receipt_id)

    if not receipt:
        storage.append_audit(
            "broker_blocked_receipt_not_found",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
            },
        )
        return {
            "executed": False,
            "reason": "receipt_not_found",
            "receipt_id": receipt_id,
        }

    # 3. Revocation check.
    if receipt.revoked:
        storage.append_audit(
            "broker_blocked_receipt_revoked",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
            },
        )
        return {
            "executed": False,
            "reason": "receipt_revoked",
            "receipt": receipt.model_dump(),
        }

    # 4. Cryptographic integrity check.
    if not receipts.verify_signature(receipt):
        storage.append_audit(
            "broker_blocked_signature_invalid",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
            },
        )
        return {
            "executed": False,
            "reason": "signature_invalid",
            "receipt": receipt.model_dump(),
        }

    # 5. Time-bound validity check.
    if receipts.is_expired(receipt):
        storage.append_audit(
            "broker_blocked_receipt_expired",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
            },
        )
        return {
            "executed": False,
            "reason": "receipt_expired",
            "receipt": receipt.model_dump(),
        }

    # 6. Exact action/agent binding check.
    if not receipts.verify_action_binding(receipt, req):
        storage.append_audit(
            "broker_blocked_action_mismatch",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
                "action_type": req.action_type,
            },
        )
        return {
            "executed": False,
            "reason": "action_binding_mismatch",
            "receipt": receipt.model_dump(),
        }

    # 7. SSRF check — the execution_webhook is caller-supplied and must not
    #    point at internal/private network infrastructure.
    is_safe, webhook_reason = url_safety.validate_webhook_url(execution_webhook)
    if not is_safe:
        storage.append_audit(
            "broker_blocked_unsafe_webhook",
            {
                "agent_id": req.agent_id,
                "receipt_id": receipt_id,
                "reason": webhook_reason,
            },
        )
        return {
            "executed": False,
            "reason": f"unsafe_execution_webhook:{webhook_reason}",
            "receipt": receipt.model_dump(),
        }

    # 8. Only after ALL checks pass may execution occur.
    execution_result = None
    executed = False

    try:
        # follow_redirects=False is deliberate: a webhook URL that passed
        # the SSRF check above could still redirect to an internal address
        # at request time. We refuse to follow any redirect rather than
        # re-validating a moving target.
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.post(
                execution_webhook,
                json={
                    "action_id": receipt.action_id,
                    "receipt_id": receipt.receipt_id,
                    "agent_id": req.agent_id,
                    "action_type": req.action_type,
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

    storage.append_audit(
        "broker_executed",
        {
            "action_id": receipt.action_id,
            "agent_id": req.agent_id,
            "receipt_id": receipt.receipt_id,
            "executed": executed,
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
