"""Canonical action envelopes and hashes used by Cyraduct authorization.

The canonical representation is deliberately boring and deterministic: JSON
objects are sorted, separators are fixed, UTF-8 is used, and every
security-relevant request field is represented explicitly. Policy receipts and
runtime receipts use different envelopes so legacy policy receipts do not
silently acquire runtime-only fields at verification time.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal


PROTOCOL_VERSION = "1.0"
CanonicalMode = Literal["policy", "runtime"]


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON-compatible value deterministically for hashing."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def action_envelope(req: Any, action_id: str, mode: CanonicalMode = "policy") -> dict[str, Any]:
    """Build the signed security envelope for a policy or runtime request.

    ``mode=policy`` intentionally contains only fields available to the
    attested policy flow. ``mode=runtime`` adds target/state/idempotency fields
    that are evaluated by the runtime authorization layer.
    """
    envelope: dict[str, Any] = {
        "protocol_version": getattr(req, "protocol_version", PROTOCOL_VERSION),
        "request_id": getattr(req, "request_id", None),
        "action_id": action_id,
        "agent": {
            "id": req.agent_id,
            "principal": req.principal,
            "framework": req.framework,
        },
        "action": {
            "type": req.action_type,
            "consequence_class": req.consequence_class,
            "purpose": req.purpose,
            "consumer": req.consumer,
            "jurisdiction": req.jurisdiction,
            "parameters": req.payload,
        },
        "policy": {
            "pack": req.policy_pack,
        },
        "evidence_refs": list(req.evidence_refs),
        "evidence_assurance": (
            req.evidence_assurance.model_dump(exclude_none=True, by_alias=True)
            if getattr(req, "evidence_assurance", None)
            else None
        ),
    }

    if mode == "runtime":
        envelope["runtime"] = {
            "target": req.target,
            "resource": req.resource,
            "reversibility": req.reversibility,
            "authority": req.authority,
            "authorization_expires_at": req.authorization_expires_at,
            "authorized_state_version": req.authorized_state_version,
            "current_state_version": req.current_state_version,
            "idempotency_key": req.idempotency_key,
        }

    return envelope


def action_hash(req: Any, action_id: str, mode: CanonicalMode = "policy") -> str:
    """Hash the complete canonical security envelope."""
    return sha256_hex(action_envelope(req, action_id, mode))


def parameters_hash(payload: dict[str, Any]) -> str:
    """Hash action parameters using the same deterministic JSON rules."""
    return sha256_hex(payload)
