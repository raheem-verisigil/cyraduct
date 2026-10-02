"""Minimal local sink guard for a Cyraduct receipt.

The sink can run this after fetching the published public key. It does not
call Cyraduct while enforcing the signature, expiry, and optional action hash.
Revocation still requires a current revocation source or the attested verify
endpoint, depending on the deployment's threat model.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def require_receipt(
    receipt: dict[str, Any],
    public_key_b64: str,
    *,
    expected_action_hash: str | None = None,
) -> None:
    """Raise ValueError unless the receipt is locally safe to rely on."""
    try:
        receipt_id = receipt["receipt_id"]
        action_hash = receipt["action_hash"]
        expires_at = receipt["expires_at"]
        prev_hash = receipt.get("prev_receipt_hash") or ""
        signature_b64 = receipt["signature"]["value"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"malformed Cyraduct receipt: {exc}") from exc

    if expected_action_hash is not None and action_hash != expected_action_hash:
        raise ValueError("receipt action hash does not match the requested action")

    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("receipt expiry is not a valid timestamp") from exc
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("receipt is expired")

    message = f"{receipt_id}|{action_hash}|{expires_at}|{prev_hash}".encode()
    try:
        public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        public_key.verify(base64.b64decode(signature_b64), message)
    except Exception as exc:
        raise ValueError(f"receipt signature is invalid: {exc}") from exc


if __name__ == "__main__":
    print("Import require_receipt() in the downstream ERP, bank, or payment sink.")
