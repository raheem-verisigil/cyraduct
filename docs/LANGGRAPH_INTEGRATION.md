# Cyraduct + LangChain/LangGraph integration

This optional integration demonstrates a narrow, explicit guard around one
LangChain tool. It does not automatically protect every tool in a graph or
agent; an application must route each consequential action through the guard.

## Flow

```text
LangGraph node / tool call
        |
        v
POST /v1/runtime/evaluate (dedicated runtime API key)
        |
        +-- hold / deny / throttle / reauthorize --> return blocked; no executor call
        |
        +-- allow + signed receipt
                    |
                    v
          use pinned Ed25519 public key
          (loopback only: fetch /v1/public-key)
                    |
                    v
       verify signature + exact action binding
                    |
                    +-- invalid / missing --> fail closed; no executor call
                    |
                    v
       configured local action executor
```

The tool schema exposes only `action_text`. The application, not the model,
sets the agent identity, action type, consequence class, authority, target,
resource, and policy pack. Do not let untrusted model output choose its own
authority or lower its consequence class.

## Run the demo tests

Use Python 3.12 or newer and install the repository's core dependencies first:

```bash
pip install -r requirements.txt
pip install -r requirements-langgraph.txt pytest pytest-asyncio
PYTHONPATH=. pytest -q tests/integrations/test_langgraph_cyraduct.py
```

The integration tests run the real FastAPI app in-process through an ASGI
transport and use a harmless in-memory executor. They cover an allowed action,
a held action whose executor is never called, and a tampered receipt whose
signature verification fails closed. They do not call the production API,
use production secrets, contact a model provider, or perform real external
side effects.

## Minimal usage

```python
from integrations.langgraph.cyraduct_langgraph import create_cyraduct_guarded_tool
from integrations.langgraph.demo_graph import build_demo_graph

async def safe_demo_executor(payload: dict) -> dict:
    # Replace only with an application-controlled, allowlisted action handler.
    return {"accepted": True, "payload_text_length": len(payload["text"])}

guarded_tool = create_cyraduct_guarded_tool(
    base_url="https://api.cyraduct.com",
    api_key="load-from-your-secret-manager",
    agent_id="my-langgraph-agent",
    execute_action=safe_demo_executor,
    # Pin these from a separately trusted channel; do not fetch-and-trust
    # the key from the same endpoint that returns the authorization receipt.
    trusted_key_id="cyraduct-key-id-from-trusted-source",
    trusted_public_key_b64="base64-ed25519-public-key-from-trusted-source",
)
graph = build_demo_graph(guarded_tool)
result = await graph.ainvoke({"action_text": "Create a test ticket"})
print(result["tool_result"])
```

Never put a live API key or pinned key material in prompt context. Load them
from configuration or a secret manager. For remote endpoints, pin both the
Ed25519 public key and key ID from a separately trusted channel (for example,
compare a fingerprint communicated out-of-band); trusting a key fetched from
the same endpoint would not protect against endpoint/key substitution. Loopback
development tests may fetch the local test key. Before execution, the adapter
checks the receipt signature, expiry, runtime authorization type, agent and
action identifiers, consequence class, payload hash, and canonical runtime
action hash. Any mismatch fails closed.

This is a reference integration, not a security certification. Before using it
for consequential production actions, add the application's own authorization
policy, executor idempotency, bounded timeouts, audit correlation, operational
reconciliation, and integration-specific threat modeling.
