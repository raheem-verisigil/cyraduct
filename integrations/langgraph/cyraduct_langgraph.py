"""LangChain/LangGraph adapter that gates a local tool on Cyraduct runtime authorization.

This is an integration reference, not a claim that every LangGraph tool in an
application is automatically protected. Only actions routed through this tool
factory receive this guard.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

from verify_receipt import verify as verify_signed_receipt

ActionExecutor = Callable[[dict[str, Any]], Any | Awaitable[Any]]
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class CyraductError(RuntimeError):
    """Safe, non-secret-bearing integration error."""


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Cyraduct base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Cyraduct base_url must not contain credentials, query, or fragment")
    if parsed.scheme != "https" and parsed.hostname not in _LOOPBACK_HOSTS:
        raise ValueError("HTTPS is required for non-loopback Cyraduct endpoints")
    return base_url.rstrip("/")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _runtime_action_hash(action: dict[str, Any], action_id: str) -> str:
    """Mirror Cyraduct's documented runtime action envelope for binding checks."""
    envelope = {
        "protocol_version": action.get("protocol_version", "1.0"),
        "request_id": action.get("request_id"),
        "action_id": action_id,
        "agent": {
            "id": action["agent_id"],
            "principal": action.get("principal"),
            "framework": action.get("framework"),
        },
        "action": {
            "type": action["action_type"],
            "consequence_class": action["consequence_class"],
            "purpose": action.get("purpose"),
            "consumer": action.get("consumer"),
            "jurisdiction": action.get("jurisdiction"),
            "parameters": action.get("payload", {}),
        },
        "policy": {"pack": action.get("policy_pack", "generic")},
        "evidence_refs": list(action.get("evidence_refs", [])),
        "evidence_assurance": action.get("evidence_assurance"),
        "runtime": {
            "target": action.get("target"),
            "resource": action.get("resource"),
            "reversibility": action.get("reversibility", "reversible"),
            "authority": action.get("authority", "present"),
            "authorization_expires_at": action.get("authorization_expires_at"),
            "authorized_state_version": action.get("authorized_state_version"),
            "current_state_version": action.get("current_state_version"),
            "idempotency_key": action.get("idempotency_key"),
        },
    }
    return _canonical_hash(envelope)


class CyraductRuntimeClient:
    """Minimal async client for runtime authorization and trusted-key retrieval.

    Remote deployments must pin the Ed25519 public key and key ID obtained
    through a separately trusted channel. Fetching a key from the same endpoint
    as the receipt is permitted only for loopback development/testing.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        trusted_key_id: str | None = None,
        trusted_public_key_b64: str | None = None,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = _validate_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport
        parsed = urlparse(self.base_url)
        self.is_loopback = parsed.hostname in _LOOPBACK_HOSTS
        if not self.is_loopback and not api_key:
            raise ValueError("api_key is required for remote Cyraduct endpoints")
        if not self.is_loopback and not (trusted_key_id and trusted_public_key_b64):
            raise ValueError(
                "Remote Cyraduct endpoints require trusted_key_id and "
                "trusted_public_key_b64 pinned from a separately trusted channel"
            )
        if bool(trusted_key_id) != bool(trusted_public_key_b64):
            raise ValueError("Both trusted_key_id and trusted_public_key_b64 must be provided together")
        self.trusted_key_id = trusted_key_id
        self.trusted_public_key_b64 = trusted_public_key_b64

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Cyraduct-Runtime-Key"] = self.api_key
        return headers

    async def evaluate(self, action: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    f"{self.base_url}/v1/runtime/evaluate",
                    json=action,
                    headers=self._headers(),
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CyraductError("Cyraduct authorization request failed; action was not executed") from exc
        if not isinstance(result, dict) or not isinstance(result.get("decision"), str):
            raise CyraductError("Cyraduct returned an invalid authorization response")
        return result

    async def public_key(self) -> dict[str, Any]:
        if self.trusted_key_id and self.trusted_public_key_b64:
            return {
                "key_id": self.trusted_key_id,
                "alg": "Ed25519",
                "public_key_b64": self.trusted_public_key_b64,
            }
        if not self.is_loopback:
            raise CyraductError("Remote receipt verification key is not pinned; action was not executed")
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"{self.base_url}/v1/public-key",
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                result = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CyraductError("Could not retrieve Cyraduct verification key; action was not executed") from exc
        if not isinstance(result, dict) or result.get("alg", result.get("algorithm")) != "Ed25519":
            raise CyraductError("Cyraduct returned an invalid or unsupported public key")
        return result


async def _authorize_and_execute(
    *,
    client: CyraductRuntimeClient,
    action: dict[str, Any],
    execute_action: ActionExecutor,
) -> dict[str, Any]:
    """Fail closed unless the signed receipt binds to this exact proposed action."""
    decision = await client.evaluate(action)
    status = decision["decision"]
    if status != "allow":
        return {
            "executed": False,
            "decision": status,
            "reasons": decision.get("reasons", []),
            "action_id": decision.get("action_id"),
            "evidence": None,
        }

    receipt = decision.get("authorization")
    if not isinstance(receipt, dict):
        raise CyraductError("Cyraduct allowed the action without a receipt; action was not executed")
    if (
        receipt.get("decision") != "allow"
        or receipt.get("authorization_type") != "runtime"
        or receipt.get("runtime_decision") != "allow"
        or receipt.get("revoked") is True
    ):
        raise CyraductError("Receipt is not an active runtime ALLOW; action was not executed")
    action_id = decision.get("action_id")
    if not action_id or receipt.get("action_id") != action_id:
        raise CyraductError("Receipt/action ID mismatch; action was not executed")
    agent = receipt.get("agent") or {}
    action_info = receipt.get("action") or {}
    if (
        agent.get("agent_id") != action.get("agent_id")
        or agent.get("framework") != action.get("framework")
        or action_info.get("type") != action.get("action_type")
        or action_info.get("consequence_class") != action.get("consequence_class")
        or action_info.get("parameters_hash") != _canonical_hash(action.get("payload", {}))
        or receipt.get("action_hash") != _runtime_action_hash(action, action_id)
    ):
        raise CyraductError("Receipt does not bind to the requested action; action was not executed")
    try:
        expiry_text = receipt["expires_at"]
        normalized = expiry_text[:-1] + "+00:00" if expiry_text.endswith("Z") else expiry_text
        expiry = datetime.fromisoformat(normalized)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expiry:
            raise CyraductError("Receipt expired; action was not executed")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, CyraductError):
            raise
        raise CyraductError("Receipt expiry is invalid; action was not executed") from exc

    key_data = await client.public_key()
    public_key = key_data.get("public_key_b64", key_data.get("public_key"))
    if not isinstance(public_key, str) or not public_key:
        raise CyraductError("Cyraduct public key is missing; action was not executed")
    signature = receipt.get("signature")
    if not isinstance(signature, dict) or signature.get("key_id") != key_data.get("key_id"):
        raise CyraductError("Receipt key identity mismatch; action was not executed")
    valid, _reason = verify_signed_receipt(receipt, public_key)
    if not valid:
        raise CyraductError("Receipt signature verification failed; action was not executed")

    result = execute_action(action["payload"])
    if inspect.isawaitable(result):
        result = await result

    return {
        "executed": True,
        "decision": "allow",
        "action_id": action_id,
        "receipt_id": receipt.get("receipt_id"),
        "receipt_signature_verified": True,
        "receipt_action_binding_verified": True,
        "executor_result": result,
    }


def create_cyraduct_guarded_tool(
    *,
    base_url: str,
    api_key: str | None,
    agent_id: str,
    execute_action: ActionExecutor,
    action_type: str = "create_demo_ticket",
    consequence_class: str = "low_risk",
    authority: str = "present",
    target: str = "demo-sink",
    resource: str = "demo-ticket",
    policy_pack: str = "generic",
    trusted_key_id: str | None = None,
    trusted_public_key_b64: str | None = None,
    client: CyraductRuntimeClient | None = None,
):
    """Create a LangChain tool whose executor is unreachable until Cyraduct allows.

    The action type, consequence class, authority, target, resource, and policy
    pack are application-owned configuration, not model-controlled arguments.
    The model supplies only action_text, which becomes the signed payload.
    """
    runtime_client = client or CyraductRuntimeClient(
        base_url,
        api_key,
        trusted_key_id=trusted_key_id,
        trusted_public_key_b64=trusted_public_key_b64,
    )

    @tool("cyraduct_guarded_demo_action")
    async def guarded_action(action_text: str) -> str:
        """Perform the configured demo action only after Cyraduct authorizes it."""
        if not action_text.strip():
            return json.dumps({"executed": False, "reason": "empty_action_text"})
        action = {
            "agent_id": agent_id,
            "framework": "langgraph",
            "action_type": action_type,
            "consequence_class": consequence_class,
            "target": target,
            "resource": resource,
            "reversibility": "reversible",
            "authority": authority,
            "policy_pack": policy_pack,
            "payload": {"text": action_text},
            "runtime_state": {},
        }
        result = await _authorize_and_execute(
            client=runtime_client,
            action=action,
            execute_action=execute_action,
        )
        return json.dumps(result, sort_keys=True, default=str)

    return guarded_action
