"""
Receipt issuance and verification.

A receipt is the enforceable artifact in Tier 2 (Attested) and Tier 3
(Broker-Enforced) modes. It is Ed25519-signed (independently verifiable —
see crypto.py), tied to a hash of the exact action it authorizes, chained
to the agent's previous receipt for tamper evidence, and carries a
consequence-class-appropriate expiry.

A receipt valid until explicitly revoked is treated as a design flaw
(see positioning language) — every receipt MUST have a bounded expiry.
"""
from datetime import datetime, timedelta, timezone

from .config import CONSEQUENCE_CLASS_EXPIRY_SECONDS, DEFAULT_EXPIRY_SECONDS
from .models import (
    ActionRequest, Receipt, AgentInfo, ActionInfo, PolicyInfo,
    EvidenceInfo, SignatureInfo, new_id,
)
from .runtime import RuntimeActionRequest, RuntimeDecision
from . import crypto, consequence
from .canonical import action_hash as canonical_action_hash, parameters_hash


def _parameters_hash(payload: dict) -> str:
    return parameters_hash(payload)


def _action_hash(req: ActionRequest, action_id: str) -> str:
    """
    Hashes every field that can influence a policy decision, not just the
    ones that happen to be structurally prominent. This was previously
    incomplete: purpose, jurisdiction, and policy_pack could all
    participate in the ALLOW/DENY/CONDITIONAL decision at issuance (see
    policy_engine.py — purpose_missing, jurisdiction_in/missing, and the
    policy_pack itself all gate or shape the decision) without being
    part of what the receipt cryptographically bound at execution time.

    That gap was found and reported by an external adversarial reviewer
    (credited: Jake Macdonald) — a receipt issued partly on the strength
    of a stated purpose or jurisdiction could be presented at broker
    execution with a *different* purpose or jurisdiction and still pass
    verify_action_binding(), because those fields were never in the hash
    the signature covers. Fixed by binding the full decision-relevant
    surface, not just the fields that happened to be checked first.

    The canonical envelope binds principal, framework, consumer, and
    evidence_refs as security context even when a current policy pack does
    not branch on every one of them. This prevents a receipt from being
    detached from the caller context presented at evaluation time.
    """
    return canonical_action_hash(req, action_id, mode="policy")


def expiry_for(consequence_class: str) -> int:
    return CONSEQUENCE_CLASS_EXPIRY_SECONDS.get(consequence_class, DEFAULT_EXPIRY_SECONDS)


def _runtime_binding(req: RuntimeActionRequest, action_id: str) -> dict:
    return {
        "action_id": action_id,
        "agent_id": req.agent_id,
        "action_type": req.action_type,
        "consequence_class": req.consequence_class,
        "target": req.target,
        "resource": req.resource,
        "reversibility": req.reversibility,
        "authority": req.authority,
        "authorization_expires_at": req.authorization_expires_at,
        "authorized_state_version": req.authorized_state_version,
        "current_state_version": req.current_state_version,
        "policy_pack": req.policy_pack,
        "purpose": req.purpose,
        "payload": req.payload,
        "idempotency_key": req.idempotency_key,
    }


def _runtime_action_hash(req: RuntimeActionRequest, action_id: str) -> str:
    return canonical_action_hash(req, action_id, mode="runtime")


def _signature_message(receipt: Receipt) -> bytes:
    message = (
        f"{receipt.receipt_id}|{receipt.action_hash}|"
        f"{receipt.expires_at}|{receipt.prev_receipt_hash or ''}"
    )
    if receipt.authorization_type == "runtime":
        message += f"|runtime|{receipt.runtime_decision or ''}"
    return message.encode()


def issue_runtime_receipt(
    req: RuntimeActionRequest,
    decision: RuntimeDecision,
    prev_receipt_hash: str = None,
) -> Receipt:
    if decision.decision != "allow":
        raise ValueError("Only runtime allow decisions receive an execution authorization")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expiry_for(req.consequence_class))

    if req.authorization_expires_at:
        normalized = (
            req.authorization_expires_at[:-1] + "+00:00"
            if req.authorization_expires_at.endswith("Z")
            else req.authorization_expires_at
        )
        supplied_expiry = datetime.fromisoformat(normalized)
        if supplied_expiry.tzinfo is None:
            supplied_expiry = supplied_expiry.replace(tzinfo=timezone.utc)
        if supplied_expiry < expires_at:
            expires_at = supplied_expiry

    action_id = decision.action_id
    action_hash = _runtime_action_hash(req, action_id)
    score_result = consequence.score(
        req.consequence_class, req.action_type, req.payload
    )

    receipt = Receipt(
        receipt_id=new_id("rcpt"),
        action_id=action_id,
        decision="allow",
        agent=AgentInfo(
            agent_id=req.agent_id,
            principal=req.principal,
            framework=req.framework,
        ),
        action=ActionInfo(
            type=req.action_type,
            consequence_class=req.consequence_class,
            consequence_score=score_result["consequence_score"],
            score_factors=score_result["factors"],
            parameters_hash=_parameters_hash(req.payload),
        ),
        policy=PolicyInfo(
            policy_pack=req.policy_pack,
            policy_pack_version="runtime-v1",
            matched_rules=[],
            reasons=decision.reasons,
        ),
        evidence=EvidenceInfo(evidence_refs=req.evidence_refs),
        issued_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        action_hash=action_hash,
        prev_receipt_hash=prev_receipt_hash,
        signature=SignatureInfo(key_id=crypto.key_id(), value=""),
        authorization_type="runtime",
        runtime_decision="allow",
    )
    receipt.signature.value = crypto.sign(_signature_message(receipt))
    return receipt


def verify_runtime_binding(
    receipt: Receipt,
    req: RuntimeActionRequest,
) -> bool:
    if receipt.authorization_type != "runtime" or receipt.runtime_decision != "allow":
        return False
    if req.action_id != receipt.action_id:
        return False
    expected_hash = _runtime_action_hash(req, receipt.action_id)
    return (
        receipt.agent.agent_id == req.agent_id
        and receipt.action.type == req.action_type
        and receipt.action.consequence_class == req.consequence_class
        and receipt.policy.policy_pack == req.policy_pack
        and receipt.action_hash == expected_hash
    )


def verify_action_binding(receipt: Receipt, req: ActionRequest) -> bool:
    """Return True only when the presented request matches the signed receipt
    on every policy-relevant field. This stops a receipt issued for one
    action from being replayed against a different action that happens to
    share the same receipt_id — including the case where action_type,
    consequence_class, and payload are unchanged but a field that
    influenced the original policy decision (purpose, jurisdiction,
    policy_pack) has been swapped post-issuance."""
    expected_hash = _action_hash(req, receipt.action_id)
    return (
        receipt.agent.agent_id == req.agent_id
        and receipt.action.type == req.action_type
        and receipt.action.consequence_class == req.consequence_class
        and receipt.policy.policy_pack == req.policy_pack
        and receipt.action_hash == expected_hash
    )


def issue_receipt(req: ActionRequest, action_id: str, decision: str,
                   policy_pack: str, policy_pack_version: str,
                   matched_rules: list, reasons: list,
                   prev_receipt_hash: str = None) -> Receipt:
    if decision not in ("allow", "conditional"):
        raise ValueError("Receipts are only issued for allow/conditional decisions")

    now = datetime.now(timezone.utc)
    ttl = expiry_for(req.consequence_class)
    expires_at = now + timedelta(seconds=ttl)

    receipt_id = new_id("rcpt")
    action_hash = _action_hash(req, action_id)
    score_result = consequence.score(req.consequence_class, req.action_type, req.payload)

    # Sign over the fields that matter for integrity: receipt id, action
    # hash, expiry, and the previous receipt's hash (so the chain itself
    # is covered by the signature, not just individually-checkable links).
    msg = f"{receipt_id}|{action_hash}|{expires_at.isoformat()}|{prev_receipt_hash or ''}".encode()
    signature_value = crypto.sign(msg)

    return Receipt(
        receipt_id=receipt_id,
        action_id=action_id,
        decision=decision,
        agent=AgentInfo(agent_id=req.agent_id, principal=req.principal, framework=req.framework),
        action=ActionInfo(
            type=req.action_type,
            consequence_class=req.consequence_class,
            consequence_score=score_result["consequence_score"],
            score_factors=score_result["factors"],
            parameters_hash=_parameters_hash(req.payload),
        ),
        policy=PolicyInfo(
            policy_pack=policy_pack,
            policy_pack_version=policy_pack_version,
            matched_rules=matched_rules,
            reasons=reasons,
        ),
        evidence=EvidenceInfo(evidence_refs=req.evidence_refs),
        issued_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        action_hash=action_hash,
        prev_receipt_hash=prev_receipt_hash,
        signature=SignatureInfo(key_id=crypto.key_id(), value=signature_value),
        revoked=False,
    )


def verify_signature(receipt: Receipt, public_key_b64: str = None) -> bool:
    return crypto.verify(
        _signature_message(receipt),
        receipt.signature.value,
        public_key_b64,
    )


def is_expired(receipt: Receipt) -> bool:
    expires = datetime.fromisoformat(receipt.expires_at)
    return datetime.now(timezone.utc) > expires
