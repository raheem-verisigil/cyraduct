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
import hashlib
import json
from datetime import datetime, timedelta, timezone

from .config import CONSEQUENCE_CLASS_EXPIRY_SECONDS, DEFAULT_EXPIRY_SECONDS
from .models import (
    ActionRequest, Receipt, AgentInfo, ActionInfo, PolicyInfo,
    EvidenceInfo, SignatureInfo, new_id,
)
from . import crypto, consequence


def _parameters_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


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

    principal, framework, consumer, and evidence_refs are deliberately
    NOT included: none of them currently participate in any policy
    condition (see policy_engine.py's condition matcher), so binding them
    would be over-binding without a corresponding integrity claim. If a
    future policy pack gains a condition on any of these, they must be
    added here in the same change.
    """
    canonical = json.dumps(
        {
            "action_id": action_id,
            "agent_id": req.agent_id,
            "action_type": req.action_type,
            "consequence_class": req.consequence_class,
            "purpose": req.purpose,
            "jurisdiction": req.jurisdiction,
            "policy_pack": req.policy_pack,
            "payload": req.payload,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def expiry_for(consequence_class: str) -> int:
    return CONSEQUENCE_CLASS_EXPIRY_SECONDS.get(consequence_class, DEFAULT_EXPIRY_SECONDS)


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
    msg = f"{receipt.receipt_id}|{receipt.action_hash}|{receipt.expires_at}|{receipt.prev_receipt_hash or ''}".encode()
    return crypto.verify(msg, receipt.signature.value, public_key_b64)


def is_expired(receipt: Receipt) -> bool:
    expires = datetime.fromisoformat(receipt.expires_at)
    return datetime.now(timezone.utc) > expires
