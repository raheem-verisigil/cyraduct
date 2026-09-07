#!/usr/bin/env python3
"""
Standalone Cyraduct receipt verifier.

Deliberately has NO dependency on the Cyraduct server being reachable or
trusted. Give it a receipt JSON (as returned by /v1/attested/evaluate or
fetched from /v1/receipts/{id}) and a public key (from /v1/public-key),
and it verifies the signature purely with the 'cryptography' library.

This is the concrete artifact behind the claim "independently verifiable" —
an auditor can run this script on an air-gapped machine with nothing but
the receipt and the published public key.

Usage:
    python3 verify_receipt.py receipt.json public_key.txt
"""
import sys
import json
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify(receipt: dict, public_key_b64: str) -> tuple[bool, str]:
    receipt_id = receipt["receipt_id"]
    action_hash = receipt["action_hash"]
    expires_at = receipt["expires_at"]
    prev_hash = receipt.get("prev_receipt_hash") or ""
    signature_b64 = receipt["signature"]["value"]

    msg = f"{receipt_id}|{action_hash}|{expires_at}|{prev_hash}".encode()

    pub_bytes = base64.b64decode(public_key_b64)
    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

    try:
        pub_key.verify(base64.b64decode(signature_b64), msg)
        return True, "signature valid"
    except Exception as e:
        return False, f"signature invalid: {e}"


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 verify_receipt.py <receipt.json> <public_key.txt>")
        sys.exit(1)

    with open(sys.argv[1]) as f:
        payload = json.load(f)
    # Accept either a raw receipt or the {"receipt": {...}} evaluate response
    receipt = payload.get("receipt", payload)

    with open(sys.argv[2]) as f:
        public_key_b64 = f.read().strip()

    ok, reason = verify(receipt, public_key_b64)
    print(f"receipt_id: {receipt['receipt_id']}")
    print(f"valid:      {ok}")
    print(f"reason:     {reason}")
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
