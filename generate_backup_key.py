#!/usr/bin/env python3
"""
Generate a backup encryption key.

Run this ONCE. Set the output as CYRADUCT_BACKUP_ENCRYPTION_KEY on the
backup service in Railway. Losing this key means existing backups become
permanently unreadable — store it somewhere safe outside Railway too
(a password manager), the same way you'd treat the Ed25519 signing key.
"""
from cryptography.fernet import Fernet

print("Set this as CYRADUCT_BACKUP_ENCRYPTION_KEY (Railway secret, and store a copy in a password manager):")
print(Fernet.generate_key().decode())
