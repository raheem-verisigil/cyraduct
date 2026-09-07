"""
Cryptographic signing for receipts.

This is the load-bearing upgrade from the MVP: receipts were previously
signed with HMAC, which is only verifiable by Cyraduct itself (a shared
secret). That quietly contradicted any claim of independent verifiability.

Ed25519 is asymmetric: Cyraduct holds the private key, but the PUBLIC key
is published (see /v1/public-key). Anyone — an auditor, a regulator, a
customer's own tooling — can verify a receipt's signature without ever
trusting Cyraduct's server or API. That is what "independently verifiable"
has to mean to not be a marketing phrase.

Key persistence here is file-based for the reference implementation.
In a real deployment, the private key belongs in a KMS / secrets manager,
never on local disk in plaintext.
"""
import base64
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

_KEY_ID = os.environ.get("CYRADUCT_KEY_ID", "cyraduct-dev-key-1")
_PRIVATE_KEY_PATH = os.environ.get("CYRADUCT_PRIVATE_KEY_PATH", "cyraduct_ed25519_private.pem")
_PRIVATE_KEY_B64 = os.environ.get("CYRADUCT_PRIVATE_KEY_B64")  # preferred for deployed environments

_private_key: Ed25519PrivateKey = None


def _load_or_generate_key() -> Ed25519PrivateKey:
    global _private_key
    if _private_key is not None:
        return _private_key

    if _PRIVATE_KEY_B64:
        # Deployed environments (Railway, etc.): key is supplied via a
        # secret env var, so it survives redeploys and disk resets.
        # Generate one with generate_key.py and set it once as a secret.
        raw = base64.b64decode(_PRIVATE_KEY_B64)
        _private_key = Ed25519PrivateKey.from_private_bytes(raw)
    elif os.path.exists(_PRIVATE_KEY_PATH):
        with open(_PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        # Local dev fallback only. Never rely on this in a deployed
        # environment — the file will not survive a redeploy/restart on
        # most PaaS platforms, silently rotating the signing identity.
        _private_key = Ed25519PrivateKey.generate()
        pem = _private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with open(_PRIVATE_KEY_PATH, "wb") as f:
            f.write(pem)
    return _private_key


def key_id() -> str:
    return _KEY_ID


def sign(message: bytes) -> str:
    key = _load_or_generate_key()
    signature = key.sign(message)
    return base64.b64encode(signature).decode()


def public_key_b64() -> str:
    key = _load_or_generate_key()
    pub_bytes = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(pub_bytes).decode()


def verify(message: bytes, signature_b64: str, public_key_b64_str: str = None) -> bool:
    """Verify a signature. If public_key_b64_str is omitted, verifies against
    this instance's own key (useful for self-checks); a real independent
    verifier should always pass the published public key explicitly."""
    pub_b64 = public_key_b64_str or public_key_b64()
    pub_bytes = base64.b64decode(pub_b64)
    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
    try:
        pub_key.verify(base64.b64decode(signature_b64), message)
        return True
    except Exception:
        return False
