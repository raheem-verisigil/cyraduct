"""Safe live E2E: production authorization, LangGraph, in-memory sink only."""
import asyncio
import json
import os
import re

from integrations.langgraph.cyraduct_langgraph import create_cyraduct_guarded_tool
from integrations.langgraph.demo_graph import build_demo_graph


async def main():
    base_url = os.environ.get("CYRADUCT_BASE_URL", "https://api.cyraduct.com")
    api_key = os.environ["CYRADUCT_RUNTIME_API_KEY"]
    key_id = os.environ["CYRADUCT_TRUSTED_KEY_ID"]
    # The workflow validates decoded key length and an independently pinned
    # SHA-256 fingerprint. Normalize copy/paste whitespace and PEM headers for
    # the adapter/verifier, which expect Base64 of the raw 32-byte public key.
    public_key = re.sub(
        r"-----BEGIN [^-]+-----|-----END [^-]+-----", "",
        os.environ["CYRADUCT_TRUSTED_PUBLIC_KEY_B64"],
    )
    public_key = "".join(public_key.split())
    calls = []

    def sink(payload):
        calls.append(dict(payload))
        return {"accepted": True, "sink": "in-memory"}

    async def run_case(authority, agent_id, text):
        guarded = create_cyraduct_guarded_tool(
            base_url=base_url,
            api_key=api_key,
            agent_id=agent_id,
            execute_action=sink,
            authority=authority,
            trusted_key_id=key_id,
            trusted_public_key_b64=public_key,
        )
        result = await build_demo_graph(guarded).ainvoke({"action_text": text})
        return json.loads(result["tool_result"])

    before = len(calls)
    allowed = await run_case("present", "cyraduct-e2e-allow", "harmless E2E test")
    assert allowed.get("executed") is True, allowed
    assert allowed.get("decision") == "allow", allowed
    assert allowed.get("receipt_signature_verified") is True, allowed
    assert allowed.get("receipt_action_binding_verified") is True, allowed
    assert len(calls) == before + 1, "ALLOW must call only the in-memory sink once"
    print("PASS: live ALLOW, signature and action binding verified; in-memory sink called once")

    before = len(calls)
    held = await run_case("missing", "cyraduct-e2e-hold", "must remain blocked")
    assert held.get("executed") is False, held
    assert held.get("decision") == "hold", held
    assert len(calls) == before, "HOLD must not call the sink"
    print("PASS: live HOLD; in-memory sink was not called")
    print("LIVE_LANGGRAPH_E2E_PASS")
    print("Scope: production runtime API, LangGraph adapter, pinned-key receipt validation, in-memory sink.")
    print("Not tested: external business sink, model provider, multi-tenant isolation, production side effects.")


if __name__ == "__main__":
    asyncio.run(main())
