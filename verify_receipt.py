#!/usr/bin/env python3
"""
Standalone Cyraduct receipt verifier.

Deliberately has NO dependency on the Cyraduct server being reachable or
trusted. Give it a receipt JSON (as returned by /v1/attested/evaluate or
fetched from /v1/receipts/{id}) and a public key (from /v1/public-key),
and it verifies the signatures purely with the 'cryptography' library.

Two signatures may be present:
  signature     legacy: covers receipt_id | action_hash | expires_at | prev_receipt_hash
                ONLY. It does NOT authenticate `decision`, agent, action or policy metadata.
  signature_v2  covers all of those (see docs/RECEIPT_SIGNATURE_V2.md).

Use --require-v2 whenever you rely on `decision` or on any metadata field: a receipt
without a valid v2 signature is then rejected. Revocation and expiry-at-issuer still
require asking the issuer; this script only proves authenticity of what was signed.

Usage:
    python3 verify_receipt.py receipt.json public_key.txt [--require-v2]
"""
import sys
import json
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

V2_DOMAIN = b"cyraduct.receipt.v2\n"


def canonical_json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def v1_message(receipt: dict) -> bytes:
    msg = f"{receipt['receipt_id']}|{receipt['action_hash']}|{receipt['expires_at']}|{receipt.get('prev_receipt_hash') or ''}"
    if receipt.get("authorization_type") == "runtime":
        msg += f"|runtime|{receipt.get('runtime_decision') or ''}"
    return msg.encode()


def v2_message(receipt: dict) -> bytes:
    agent, action, policy = receipt.get("agent") or {}, receipt.get("action") or {}, receipt.get("policy") or {}
    core = {
        "v": 2,
        "receipt_id": receipt["receipt_id"],
        "action_id": receipt["action_id"],
        "decision": receipt["decision"],
        "authorization_type": receipt.get("authorization_type", "policy"),
        "runtime_decision": receipt.get("runtime_decision"),
        "agent": {k: agent.get(k) for k in ("agent_id", "principal", "framework")},
        "action": {k: action.get(k) for k in ("type", "consequence_class")},
        "policy": {k: policy.get(k) for k in ("policy_pack", "policy_pack_version")},
        "evidence_assurance": receipt.get("evidence_assurance"),
        "action_hash": receipt["action_hash"],
        "issued_at": receipt["issued_at"],
        "expires_at": receipt["expires_at"],
        "prev_receipt_hash": receipt.get("prev_receipt_hash"),
        "key_id": (receipt.get("signature_v2") or {}).get("key_id"),
    }
    return V2_DOMAIN + canonical_json_bytes(core)


def _check(public_key_b64: str, signature_b64: str, message: bytes) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(base64.b64decode(signature_b64), message)
        return True
    except Exception:
        return False


def verify(receipt: dict, public_key_b64: str, require_v2: bool = False) -> tuple[bool, str]:
    has_v2 = bool(receipt.get("signature_v2"))
    if require_v2 and not has_v2:
        return False, "v2 signature required but absent (legacy receipt: decision and metadata are NOT authenticated)"
    if not _check(public_key_b64, receipt["signature"]["value"], v1_message(receipt)):
        return False, "signature invalid (legacy)"
    if has_v2:
        if not _check(public_key_b64, receipt["signature_v2"]["value"], v2_message(receipt)):
            return False, "signature_v2 invalid: decision or metadata do not match what was signed"
        return True, "signature and signature_v2 valid"
    return True, "legacy signature valid (decision and metadata NOT authenticated)"


def main():
    args = [a for a in sys.argv[1:] if a != "--require-v2"]
    if len(args) != 2:
        print("Usage: python3 verify_receipt.py <receipt.json> <public_key.txt> [--require-v2]")
        sys.exit(1)

    with open(args[0]) as f:
        payload = json.load(f)
    # Accept either a raw receipt or the {"receipt": {...}} evaluate response
    receipt = payload.get("receipt", payload)

    with open(args[1]) as f:
        public_key_b64 = f.read().strip()

    ok, reason = verify(receipt, public_key_b64, require_v2="--require-v2" in sys.argv)
    print(f"receipt_id: {receipt['receipt_id']}")
    print(f"valid:      {ok}")
    print(f"reason:     {reason}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
