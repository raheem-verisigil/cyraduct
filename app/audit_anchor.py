"""Optional external anchor for the latest audit-log hash.

Configure CYRADUCT_AUDIT_ANCHOR_URL and optionally
CYRADUCT_AUDIT_ANCHOR_TOKEN in production. The endpoint should durably record
the latest hash and timestamp outside the application database.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)


def anchor_latest_hash(entry_hash: str, sequence: int | None = None) -> bool:
    url = os.getenv("CYRADUCT_AUDIT_ANCHOR_URL")
    if not url:
        return False
    headers = {"Content-Type": "application/json"}
    token = os.getenv("CYRADUCT_AUDIT_ANCHOR_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.post(url, headers=headers, json={"entry_hash": entry_hash, "sequence": sequence}, timeout=3.0)
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.exception("Audit hash anchor failed")
        return False
