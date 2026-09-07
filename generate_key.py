#!/usr/bin/env python3
"""
Generate a Cyraduct signing keypair for deployment.

Run this ONCE before your first real deploy. Set the printed private key
as a Railway environment variable (CYRADUCT_PRIVATE_KEY_B64) so it stays
stable across redeploys — publish the public key wherever verifiers will
look for it (the site's /v1/public-key mirrors whatever key the server
is actually using, so this is mainly for your own records / rotation).

Usage:
    python3 generate_key.py
"""
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

key = Ed25519PrivateKey.generate()

private_raw = key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
public_raw = key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)

print("Set this as a Railway secret env var — CYRADUCT_PRIVATE_KEY_B64:")
print(base64.b64encode(private_raw).decode())
print()
print("Corresponding public key (for your own records; the live server")
print("also serves this at GET /v1/public-key once deployed):")
print(base64.b64encode(public_raw).decode())
