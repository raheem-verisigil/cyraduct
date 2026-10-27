import json

import httpx
import pytest
from langgraph.graph import END, StateGraph

from app import config, storage
from main import app
from integrations.langgraph.cyraduct_langgraph import (
    CyraductError,
    CyraductRuntimeClient,
    create_cyraduct_guarded_tool,
)
from integrations.langgraph.demo_graph import build_demo_graph


@pytest.fixture
def app_transport(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "RUNTIME_API_KEY", "langgraph-test-key")
    monkeypatch.setattr(storage, "get_kill_switch", lambda: {"active": False, "reason": None})
    monkeypatch.setattr(storage, "get_last_receipt_hash", lambda _agent_id: None)
    monkeypatch.setattr(storage, "save_receipt", lambda _receipt: None)
    monkeypatch.setattr(storage, "append_audit", lambda *_args, **_kwargs: None)
    return httpx.ASGITransport(app=app)


@pytest.mark.asyncio
async def test_langgraph_allowed_action_verifies_receipt_before_execution(app_transport):
    executed = []
    client = CyraductRuntimeClient(
        "http://localhost",
        "langgraph-test-key",
        transport=app_transport,
    )

    async def execute_action(payload):
        executed.append(payload)
        return {"ticket": "DEMO-001"}

    guarded = create_cyraduct_guarded_tool(
        base_url="http://localhost",
        api_key="langgraph-test-key",
        agent_id="test-langgraph-allowed",
        execute_action=execute_action,
        client=client,
    )
    graph = build_demo_graph(guarded)
    result = await graph.ainvoke({"action_text": "Create a harmless test ticket"})

    tool_result = json.loads(result["tool_result"])
    assert tool_result["executed"] is True
    assert tool_result["decision"] == "allow"
    assert tool_result["receipt_signature_verified"] is True
    assert tool_result["receipt_id"]
    assert executed == [{"text": "Create a harmless test ticket"}]


@pytest.mark.asyncio
async def test_langgraph_denied_action_never_reaches_executor(app_transport):
    executed = []
    client = CyraductRuntimeClient(
        "http://localhost",
        "langgraph-test-key",
        transport=app_transport,
    )

    guarded = create_cyraduct_guarded_tool(
        base_url="http://localhost",
        api_key="langgraph-test-key",
        agent_id="test-langgraph-denied",
        execute_action=lambda payload: executed.append(payload),
        authority="missing",
        client=client,
    )
    graph = build_demo_graph(guarded)
    result = await graph.ainvoke({"action_text": "This must not execute"})

    tool_result = json.loads(result["tool_result"])
    assert tool_result["executed"] is False
    assert tool_result["decision"] == "hold"
    assert executed == []


@pytest.mark.asyncio
async def test_tampered_receipt_fails_closed_before_executor(app_transport):
    executed = []
    client = CyraductRuntimeClient(
        "http://localhost",
        "langgraph-test-key",
        transport=app_transport,
    )
    original_evaluate = client.evaluate

    async def tampered_evaluate(action):
        result = await original_evaluate(action)
        result["authorization"]["action_hash"] = "tampered"
        return result

    client.evaluate = tampered_evaluate

    guarded = create_cyraduct_guarded_tool(
        base_url="http://localhost",
        api_key="langgraph-test-key",
        agent_id="test-langgraph-tampered",
        execute_action=lambda payload: executed.append(payload),
        client=client,
    )
    graph = build_demo_graph(guarded)

    with pytest.raises(CyraductError, match="signature verification failed"):
        await graph.ainvoke({"action_text": "Tampered evidence must not execute"})
    assert executed == []


@pytest.mark.asyncio
async def test_remote_endpoint_requires_https_and_key():
    with pytest.raises(ValueError, match="HTTPS"):
        CyraductRuntimeClient("http://cyraduct.example.com", "key")
    with pytest.raises(ValueError, match="api_key"):
        CyraductRuntimeClient("https://cyraduct.example.com")
