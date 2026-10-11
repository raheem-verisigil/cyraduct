"""Minimal local sink guard for a Cyraduct receipt.

The sink can run this after fetching the published public key. It does not
call Cyraduct while enforcing the signatures, expiry, and optional action hash.
Revocation still requires a current revocation source or the attested verify
endpoint, depending on the deployment's threat model.

The legacy `signature` does NOT authenticate `decision` or the agent/action/policy
metadata, so a sink that reads those fields from a presented receipt could be fooled
by whoever presents it. This guard therefore requires the v2 signature by default
(docs/RECEIPT_SIGNATURE_V2.md) and only then trusts `decision`.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

V2_DOMAIN = b"cyraduct.receipt.v2\n"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _v2_message(r: dict[str, Any]) -> bytes:
    agent, action, policy = r.get("agent") or {}, r.get("action") or {}, r.get("policy") or {}
    return V2_DOMAIN + _canonical({
        "v": 2, "receipt_id": r["receipt_id"], "action_id": r["action_id"], "decision": r["decision"],
        "authorization_type": r.get("authorization_type", "policy"), "runtime_decision": r.get("runtime_decision"),
        "agent": {k: agent.get(k) for k in ("agent_id", "principal", "framework")},
        "action": {k: action.get(k) for k in ("type", "consequence_class")},
        "policy": {k: policy.get(k) for k in ("policy_pack", "policy_pack_version")},
        "evidence_assurance": r.get("evidence_assurance"),
        "action_hash": r["action_hash"], "issued_at": r["issued_at"], "expires_at": r["expires_at"],
        "prev_receipt_hash": r.get("prev_receipt_hash"), "key_id": (r.get("signature_v2") or {}).get("key_id"),
    })


def require_receipt(
    receipt: dict[str, Any],
    public_key_b64: str,
    *,
    expected_action_hash: str | None = None,
    allow_conditional: bool = False,
    allow_legacy: bool = False,
) -> None:
    """Raise ValueError unless the receipt is locally safe to rely on.

    allow_legacy=True accepts receipts that carry only the legacy signature. Their
    `decision` and metadata are unauthenticated, so use it only for a short migration
    window, and confirm the decision with the issuer (GET /v1/attested/verify/{id})."""
    try:
        receipt_id = receipt["receipt_id"]
        action_hash = receipt["action_hash"]
        expires_at = receipt["expires_at"]
        prev_hash = receipt.get("prev_receipt_hash") or ""
        signature_b64 = receipt["signature"]["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"malformed Cyraduct receipt: {exc}") from exc

    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    except Exception as exc:
        raise ValueError(f"invalid public key: {exc}") from exc

    sig2 = receipt.get("signature_v2")
    if sig2 is None and not allow_legacy:
        raise ValueError("receipt has no v2 signature: its decision and metadata cannot be trusted")
    if sig2 is not None:
        try:
            public_key.verify(base64.b64decode(sig2["value"]), _v2_message(receipt))
        except Exception as exc:
            raise ValueError(f"receipt v2 signature is invalid (decision or metadata altered?): {exc}") from exc

    if receipt.get("decision") == "conditional" and not allow_conditional:
        raise ValueError("conditional receipt requires human approval before the sink may act")

    if expected_action_hash is not None and action_hash != expected_action_hash:
        raise ValueError("receipt action hash does not match the requested action")

    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("receipt expiry is not a valid timestamp") from exc
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("receipt is expired")

    message = f"{receipt_id}|{action_hash}|{expires_at}|{prev_hash}"
    if receipt.get("authorization_type") == "runtime":
        message += f"|runtime|{receipt.get('runtime_decision') or ''}"
    try:
        public_key.verify(base64.b64decode(signature_b64), message.encode())
    except Exception as exc:
        raise ValueError(f"receipt signature is invalid: {exc}") from exc


if __name__ == "__main__":
    print("Import require_receipt() in the downstream ERP, bank, or payment sink.")
