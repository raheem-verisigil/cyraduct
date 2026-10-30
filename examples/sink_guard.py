"""Minimal local sink guard for a Cyraduct receipt.

Uses the same canonical Ed25519 verifier as the standalone audit utility.
The sink does not need to call Cyraduct to verify immutable receipt claims,
signature, expiry, and an optional expected action hash. Revocation and
consumption still require a current trusted lifecycle source or a broker
protocol; a self-contained signed receipt cannot prove it has not since been
revoked.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from verify_receipt import verify as verify_signature


def require_receipt(
    receipt: dict[str, Any],
    public_key_b64: str,
    *,
    expected_action_hash: str | None = None,
) -> None:
    """Raise ValueError unless the receipt's signed claims and expiry verify."""
    try:
        action_hash = receipt["action_hash"]
        expires_at = receipt["expires_at"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"malformed Cyraduct receipt: {exc}") from exc

    if expected_action_hash is not None and action_hash != expected_action_hash:
        raise ValueError("receipt action hash does not match the requested action")

    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("receipt expiry is not a valid timestamp") from exc
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("receipt is expired")

    valid, reason = verify_signature(receipt, public_key_b64)
    if not valid:
        raise ValueError(f"receipt signature is invalid: {reason}")


if __name__ == "__main__":
    print("Import require_receipt() in the downstream ERP, bank, or payment sink.")
