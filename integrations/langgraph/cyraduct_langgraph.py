"""LangChain/LangGraph adapter that gates a local tool on Cyraduct runtime authorization.

This is an integration reference, not a claim that every LangGraph tool in an
application is automatically protected. Only actions routed through this tool
factory receive this guard.
"""
from __future__ import annotations

import inspect
import json
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

from verify_receipt import verify as verify_signed_receipt

ActionExecutor = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class CyraductError(RuntimeError):
    """Safe, non-secret-bearing integration error."""


def _validate_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Cyraduct base_url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Cyraduct base_url must not contain credentials, query, or fragment")
    is_loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not is_loopback:
        raise ValueError("HTTPS is required for non-loopback Cyraduct endpoints")
    return base_url.rstrip("/")


class CyraductRuntimeClient:
    """Minimal async client for runtime authorization and published-key retrieval."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = _validate_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport
        parsed = urlparse(self.base_url)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and not api_key:
            raise ValueError("api_key is required for remote Cyraduct endpoints")

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
        if not isinstance(result, dict):
            raise CyraductError("Cyraduct returned an invalid public-key response")
        if result.get("alg", result.get("algorithm")) != "Ed25519":
            raise CyraductError("Unsupported Cyraduct receipt-signing algorithm")
        return result


async def _authorize_and_execute(
    *,
    client: CyraductRuntimeClient,
    action: dict[str, Any],
    execute_action: ActionExecutor,
) -> dict[str, Any]:
    """Fail closed: no executor call unless decision and signed receipt validate."""
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
        "action_id": decision.get("action_id"),
        "receipt_id": receipt.get("receipt_id"),
        "receipt_signature_verified": True,
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
    client: CyraductRuntimeClient | None = None,
):
    """Create a LangChain tool whose executor is unreachable until Cyraduct allows.

    The action type, consequence class, authority, target and resource are
    server/application-owned configuration, not model-controlled arguments.
    The model supplies only action_text, which becomes the signed payload.
    """
    runtime_client = client or CyraductRuntimeClient(base_url, api_key)

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
