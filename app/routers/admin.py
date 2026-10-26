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
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional
from .. import storage, auth, config, crypto

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
def get_kill_switch(x_cyraduct_admin_key: Optional[str] = Header(None)):
    auth.require_full_admin(x_cyraduct_admin_key)
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


class TenantCreateRequest(BaseModel):
    name: str


@router.post("/tenants")
def create_tenant(body: TenantCreateRequest, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Provision a tenant. The API key is returned exactly once; only its
    hash is stored. Full admin only."""
    auth.require_full_admin(x_cyraduct_admin_key)
    tenant = storage.create_tenant(body.name.strip()[:120] or "unnamed")
    storage.append_audit("tenant_created", {"tenant_id": tenant["tenant_id"], "name": tenant["name"]})
    return tenant


@router.get("/tenants")
def list_tenants(x_cyraduct_admin_key: Optional[str] = Header(None)):
    auth.require_full_admin(x_cyraduct_admin_key)
    return {"tenants": storage.list_tenants()}


@router.post("/tenants/{tenant_id}/revoke")
def revoke_tenant(tenant_id: str, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Disable a tenant's key and revoke every receipt it holds."""
    auth.require_full_admin(x_cyraduct_admin_key)
    if not storage.revoke_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    storage.append_audit("tenant_revoked", {"tenant_id": tenant_id})
    return {"tenant_id": tenant_id, "revoked": True}


@router.get("/posture")
def security_posture(request: Request, x_cyraduct_admin_key: Optional[str] = Header(None)):
    """Read-only deployment self-check for operators. Reports booleans and
    names only -- never a secret value -- so it is safe to paste into a
    ticket. Lets you confirm production configuration with one request and
    without any startup-crash risk."""
    auth.require_full_admin(x_cyraduct_admin_key)
    findings = []
    if config.ENVIRONMENT != "production":
        findings.append("CYRADUCT_ENV is not 'production'")
    if config.ADMIN_API_KEY in {"", "dev-insecure-admin-key"}:
        findings.append("admin key is the insecure default")
    if config.SIGNING_SECRET in {"", "dev-insecure-secret-change-me"}:
        findings.append("signing secret is the insecure default")
    if crypto.key_source() != "env":
        findings.append("signing key is not supplied via CYRADUCT_PRIVATE_KEY_B64 (may rotate on redeploy)")
    if not config.REQUIRE_TENANT_AUTH:
        findings.append("tenant authentication is not required (CYRADUCT_REQUIRE_TENANT_AUTH=false)")
    if not config.CLIENT_IP_HEADER:
        findings.append("rate limits key on the socket address; behind a proxy this may be shared by all callers")
    if not config.TEST_ADMIN_KEY:
        pass  # unset is the safe state
    return {
        "environment": config.ENVIRONMENT,
        "admin_key_is_default": config.ADMIN_API_KEY in {"", "dev-insecure-admin-key"},
        "signing_secret_is_default": config.SIGNING_SECRET in {"", "dev-insecure-secret-change-me"},
        "signing_key_source": crypto.key_source(),
        "require_tenant_auth": config.REQUIRE_TENANT_AUTH,
        "test_key_configured": bool(config.TEST_ADMIN_KEY),
        "client_ip_header": config.CLIENT_IP_HEADER or None,
        "client_ip_seen_by_rate_limiter": limiter_key(request),
        "socket_peer": request.client.host if request.client else None,
        "forwarded_headers_present": {
            h: bool(request.headers.get(h))
            for h in ("x-forwarded-for", "x-real-ip", "x-forwarded-proto", "forwarded")
        },
        "tenants": len(storage.list_tenants()),
        "findings": findings,
        "ready_for_production": not findings,
    }


def limiter_key(request: Request) -> str:
    from ..rate_limit import client_key
    return client_key(request)
