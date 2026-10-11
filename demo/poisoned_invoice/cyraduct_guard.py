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
    """Mirrors app/canonical.py (policy mode, protocol 1.0). A regression test compares this with
    the server's receipt.action_hash so it cannot silently drift again."""
    envelope = {
        "protocol_version": req.get("protocol_version") or "1.0", "request_id": req.get("request_id"),
        "action_id": action_id,
        "agent": {"id": req["agent_id"], "principal": req.get("principal"), "framework": req.get("framework")},
        "action": {"type": req["action_type"], "consequence_class": req["consequence_class"],
                   "purpose": req.get("purpose"), "consumer": req.get("consumer"),
                   "jurisdiction": req.get("jurisdiction"), "parameters": req.get("payload", {})},
        "policy": {"pack": req.get("policy_pack", "generic")},
        "evidence_refs": list(req.get("evidence_refs") or []),
        "evidence_assurance": req.get("evidence_assurance") or None,
    }
    canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _v2_message(r: Dict[str, Any]) -> bytes:
    """Mirrors docs/RECEIPT_SIGNATURE_V2.md: the fields below are what signature_v2 authenticates."""
    agent, action, policy = r.get("agent") or {}, r.get("action") or {}, r.get("policy") or {}
    core = {
        "v": 2, "receipt_id": r["receipt_id"], "action_id": r["action_id"], "decision": r["decision"],
        "authorization_type": r.get("authorization_type", "policy"), "runtime_decision": r.get("runtime_decision"),
        "agent": {k: agent.get(k) for k in ("agent_id", "principal", "framework")},
        "action": {k: action.get(k) for k in ("type", "consequence_class")},
        "policy": {k: policy.get(k) for k in ("policy_pack", "policy_pack_version")},
        "evidence_assurance": r.get("evidence_assurance"),
        "action_hash": r["action_hash"], "issued_at": r["issued_at"], "expires_at": r["expires_at"],
        "prev_receipt_hash": r.get("prev_receipt_hash"), "key_id": (r.get("signature_v2") or {}).get("key_id"),
    }
    return b"cyraduct.receipt.v2\n" + json.dumps(core, sort_keys=True, separators=(",", ":"),
                                                  ensure_ascii=False, allow_nan=False).encode("utf-8")


def verify_signature(receipt: Dict[str, Any], public_key_b64: str, require_v2: bool = False) -> Tuple[bool, str]:
    """Checks the legacy signature and, when present, signature_v2. With require_v2=True a receipt
    that lacks a valid v2 signature is refused, because only v2 authenticates `decision` and metadata."""
    key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
    v2 = receipt.get("signature_v2")
    if require_v2 and not v2:
        return False, "legacy_receipt_without_v2_signature"
    msg = (f"{receipt['receipt_id']}|{receipt['action_hash']}|{receipt['expires_at']}|"
           f"{receipt.get('prev_receipt_hash') or ''}").encode()
    if receipt.get("authorization_type") == "runtime":
        msg += f"|runtime|{receipt.get('runtime_decision') or ''}".encode()
    try:
        key.verify(base64.b64decode(receipt["signature"]["value"]), msg)
    except Exception as e:
        return False, f"signature invalid ({type(e).__name__})"
    if v2:
        try:
            key.verify(base64.b64decode(v2["value"]), _v2_message(receipt))
        except Exception as e:
            return False, f"signature_v2 invalid ({type(e).__name__}): decision or metadata altered"
        return True, "signature valid (v2)"
    return True, "signature valid (legacy: decision unauthenticated)"


def verify_at_sink(receipt: Optional[Dict[str, Any]], req: Dict[str, Any], public_key_b64: str,
                   client: Optional[CyraductClient] = None,
                   human_approved: bool = False) -> Tuple[bool, str]:
    """Everything a compliant Tier-2 sink should check before acting."""
    if not receipt:
        return False, "no_receipt_presented"
    ok, why = verify_signature(receipt, public_key_b64, require_v2=True)
    if not ok:
        return False, "signature_invalid" if "invalid" in why else why
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
