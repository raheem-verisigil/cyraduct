"""
Admin — kill switch and audit log.

Directly answers: "who has the power to turn Cyraduct off, and is that
logged?" The kill switch writes into the same hash-chained audit log as
every other event, so its use is exactly as tamper-evident as everything
else in the system.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from .. import storage
from ..config import ADMIN_API_KEY

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = None


def _check_admin(key: Optional[str]):
    if key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing admin key")


@router.post("/kill-switch")
def set_kill_switch(body: KillSwitchRequest, x_cyraduct_admin_key: Optional[str] = Header(None)):
    _check_admin(x_cyraduct_admin_key)
    storage.set_kill_switch(body.active, body.reason)
    storage.append_audit("kill_switch_changed", {"active": body.active, "reason": body.reason})
    return {"active": body.active, "reason": body.reason}


@router.get("/kill-switch")
def get_kill_switch():
    return storage.get_kill_switch()


@router.get("/audit-log")
def audit_log(limit: int = 200, x_cyraduct_admin_key: Optional[str] = Header(None)):
    _check_admin(x_cyraduct_admin_key)
    return {
        "chain_valid": storage.verify_audit_chain(),
        "entries": storage.get_audit_log(limit=limit),
    }
