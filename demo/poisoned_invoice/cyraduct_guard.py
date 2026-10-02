"""
cyraduct_guard - thin client for putting Cyraduct in front of an agent tool.

Two halves, matching the two places enforcement happens:

  AGENT SIDE  CyraductClient.authorize(...)   -> Authorization or raises ActionDenied
  SINK SIDE   verify_at_sink(...)             -> (ok, reason); the tool that moves money
                                                 / deletes data calls this before acting

The action-hash recomputation below MIRRORS app/receipts.py:_action_hash.
If that function changes (e.g. new bound fields), change it here in the same
commit. The intended fix is for Cyraduct to expose this in an official SDK.
"""
import base64
import functools
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class ActionDenied(Exception):
    def __init__(self, result: Dict[str, Any]):
        self.result = result
        d = result["decision"]
        super().__init__(f"denied by {d['policy_pack']}: {'; '.join(d['reasons'])}")


@dataclass
class Authorization:
    request: Dict[str, Any]
    result: Dict[str, Any]

    @property
    def receipt(self) -> Dict[str, Any]:
        return self.result["receipt"]

    @property
    def decision(self) -> str:
        return self.result["decision"]["decision"]


class CyraductClient:
    def __init__(self, base_url: str, admin_key: Optional[str] = None, timeout: float = 10.0):
        self.base = base_url.rstrip("/")
        self.admin_key = admin_key
        self.http = httpx.Client(timeout=timeout)

    def _admin(self):
        return {"x-cyraduct-admin-key": self.admin_key} if self.admin_key else {}

    def public_key(self) -> str:
        return self.http.get(f"{self.base}/v1/public-key").json()["public_key_b64"]

    def evaluate(self, req: Dict[str, Any]) -> Dict[str, Any]:
        r = self.http.post(f"{self.base}/v1/attested/evaluate", json=req)
        r.raise_for_status()
        return r.json()

    def authorize(self, req: Dict[str, Any]) -> Authorization:
        result = self.evaluate(req)
        if result["decision"]["decision"] == "deny":
            raise ActionDenied(result)
        return Authorization(req, result)

    def server_verify(self, receipt_id: str) -> Dict[str, Any]:
        return self.http.get(f"{self.base}/v1/attested/verify/{receipt_id}").json()

    def revoke_agent(self, agent_id: str, reason: str) -> Dict[str, Any]:
        r = self.http.post(f"{self.base}/v1/attested/revoke-agent/{agent_id}",
                           params={"reason": reason}, headers=self._admin())
        r.raise_for_status()
        return r.json()

    def receipts_for(self, agent_id: str) -> list:
        return self.http.get(f"{self.base}/v1/receipts", params={"agent_id": agent_id}).json()["receipts"]

    def audit_log(self) -> Optional[Dict[str, Any]]:
        if not self.admin_key:
            return None
        r = self.http.get(f"{self.base}/v1/admin/audit-log", headers=self._admin())
        return r.json() if r.status_code == 200 else None

    def guard(self, *, agent_id: str, action_type: str, consequence_class: str,
              policy_pack: str, enrich: Optional[Callable[[dict], dict]] = None):
        """Decorator: authorize before the tool body runs. The tool receives the
        Authorization as its first argument. `enrich` runs in trusted code and may
        add facts the model cannot forge (e.g. allowlist lookups) to the payload."""
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*, purpose=None, jurisdiction=None, **payload):
                if enrich:
                    payload.update(enrich(payload))
                req = dict(agent_id=agent_id, action_type=action_type,
                           consequence_class=consequence_class, purpose=purpose,
                           jurisdiction=jurisdiction, policy_pack=policy_pack, payload=payload)
                return fn(self.authorize(req), **payload)
            return wrapper
        return deco


def action_hash(action_id: str, req: Dict[str, Any]) -> str:
    canonical = json.dumps({
        "action_id": action_id, "agent_id": req["agent_id"],
        "action_type": req["action_type"], "consequence_class": req["consequence_class"],
        "purpose": req.get("purpose"), "jurisdiction": req.get("jurisdiction"),
        "policy_pack": req.get("policy_pack", "generic"), "payload": req.get("payload", {}),
    }, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_signature(receipt: Dict[str, Any], public_key_b64: str) -> Tuple[bool, str]:
    msg = (f"{receipt['receipt_id']}|{receipt['action_hash']}|{receipt['expires_at']}|"
           f"{receipt.get('prev_receipt_hash') or ''}").encode()
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(
            base64.b64decode(receipt["signature"]["value"]), msg)
        return True, "signature valid"
    except Exception as e:
        return False, f"signature invalid ({type(e).__name__})"


def verify_at_sink(receipt: Optional[Dict[str, Any]], req: Dict[str, Any], public_key_b64: str,
                   client: Optional[CyraductClient] = None,
                   human_approved: bool = False) -> Tuple[bool, str]:
    """Everything a compliant Tier-2 sink should check before acting."""
    if not receipt:
        return False, "no_receipt_presented"
    ok, why = verify_signature(receipt, public_key_b64)
    if not ok:
        return False, "signature_invalid"
    if datetime.now(timezone.utc) > datetime.fromisoformat(receipt["expires_at"]):
        return False, "receipt_expired"
    if (receipt["agent"]["agent_id"] != req["agent_id"]
            or receipt["action"]["type"] != req["action_type"]
            or receipt["action"]["consequence_class"] != req["consequence_class"]
            or receipt["policy"]["policy_pack"] != req.get("policy_pack", "generic")
            or receipt["action_hash"] != action_hash(receipt["action_id"], req)):
        return False, "action_binding_mismatch"
    if receipt["decision"] == "conditional" and not human_approved:
        return False, "conditional_receipt_requires_human_approval"
    if client is not None:  # revocation lives on the server
        v = client.server_verify(receipt["receipt_id"])
        if not v["valid"]:
            return False, v["reason"]
    return True, "ok"
