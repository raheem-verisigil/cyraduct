"""
Admin — kill switch and audit log.

Directly answers: "who has the power to turn Cyraduct off, and is that
logged?" The kill switch writes into the same hash-chained audit log as
every other event, so its use is exactly as tamper-evident as everything
else in the system.

The kill switch is reachable ONLY with the full admin key — never the
scoped test key (see app/auth.py). Cyraduct has no separate staging
environment, so the kill switch can halt the live service for every real
caller; that capability is deliberately kept out of reach of any
external/automated test harness, however well-intentioned.
"""
import json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from .. import storage, auth, config

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


@router.post("/kill-switch")
def set_kill_switch(body: KillSwitchRequest, x_cyraduct_admin_key: Optional[str] = Header(None)):
    auth.require_full_admin(x_cyraduct_admin_key)  # full admin only — never the test key
    storage.set_kill_switch(body.active, body.reason)
    storage.append_audit("kill_switch_changed", {"active": body.active, "reason": body.reason})
    return {"active": body.active, "reason": body.reason}


@router.get("/kill-switch")
def get_kill_switch():
    return storage.get_kill_switch()


def _entry_agent_id(entry: dict) -> Optional[str]:
    try:
        detail = json.loads(entry.get("detail", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None
    return detail.get("agent_id")


@router.get("/audit-log")
def audit_log(limit: int = 200, x_cyraduct_admin_key: Optional[str] = Header(None)):
    result = auth.check_admin_or_test_key(x_cyraduct_admin_key)
    if not result.authenticated:
        raise HTTPException(status_code=401, detail="Invalid or missing admin/test key")

    entries = storage.get_audit_log(limit=limit)

    if result.is_full_admin:
        return {"chain_valid": storage.verify_audit_chain(), "entries": entries}

    # Test key: only entries whose agent_id is in the test namespace.
    # Chain validity itself is reported (doesn't leak entry content), but
    # the entries returned are filtered.
    filtered = [e for e in entries if (aid := _entry_agent_id(e)) and auth.is_test_namespace(aid)]
    return {"chain_valid": storage.verify_audit_chain(), "entries": filtered, "note": "filtered to test namespace (scoped test key)"}
