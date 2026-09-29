# Runtime authorization -> broker enforcement tests.
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from main import app
from app import receipts, storage
from app.routers import broker

client = TestClient(app)

import pytest

@pytest.fixture(autouse=True)
def reset_broker_rate_limit():
    broker.limiter.reset()
    yield
    broker.limiter.reset()

def _request(**overrides):
    body = {
        "agent_id": "runtime-broker-test-agent",
        "action_type": "update_customer_record",
        "consequence_class": "generic_tool_call",
        "target": "crm",
        "resource": "customer/123",
        "reversibility": "reversible",
        "authority": "present",
        "authorized_state_version": "state-1",
        "current_state_version": "state-1",
        "policy_pack": "generic",
        "purpose": "sync customer profile",
        "payload": {"field": "phone", "value": "+234000000000"},
        "runtime_state": {},
    }
    body.update(overrides)
    return body

def _allow():
    r = client.post("/v1/runtime/evaluate", json=_request())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "allow"
    assert body["authorization"]["authorization_type"] == "runtime"
    assert body["authorization"]["runtime_decision"] == "allow"
    return body["authorization"]

class FakeResponse:
    status_code = 200
    text = "ok"

class FakeAsyncClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def post(self, url, json):
        return FakeResponse()

def _broker_payload(auth, **overrides):
    return _request(action_id=auth["action_id"], **overrides)

def test_runtime_allow_creates_signed_execution_authorization():
    auth = _allow()
    stored = storage.get_receipt(auth["receipt_id"])
    assert stored is not None
    assert stored.authorization_type == "runtime"
    assert stored.runtime_decision == "allow"
    assert receipts.verify_signature(stored)

def test_non_allow_runtime_decisions_create_no_authorization():
    for override in (
        {"authority": "missing"},
        {"runtime_state": {"actions_last_minute": 75}},
        {"authorized_state_version": "state-1", "current_state_version": "state-2"},
        {"authorization_expires_at": "2020-01-01T00:00:00+00:00"},
    ):
        r = client.post("/v1/runtime/evaluate", json=_request(**override))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision"] != "allow"
        assert body["authorization"] is None

def test_matching_runtime_authorization_reaches_broker(monkeypatch):
    auth = _allow()
    monkeypatch.setattr(broker.httpx, "AsyncClient", FakeAsyncClient)
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth),
    )
    assert r.status_code == 200, r.text
    assert r.json()["executed"] is True

def test_changed_state_is_blocked():
    auth = _allow()
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth, current_state_version="state-2"),
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "runtime_binding_mismatch"

def test_changed_target_is_blocked():
    auth = _allow()
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth, target="payments"),
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "runtime_binding_mismatch"

def test_changed_authority_or_reversibility_is_blocked():
    auth = _allow()
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth, authority="delegated"),
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "runtime_binding_mismatch"

    auth2 = _allow()
    r2 = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth2["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth2, reversibility="irreversible"),
    )
    assert r2.status_code == 200
    assert r2.json()["reason"] == "runtime_binding_mismatch"

def test_expired_runtime_authorization_is_blocked(monkeypatch):
    auth = _allow()
    monkeypatch.setattr(receipts, "is_expired", lambda receipt: True)
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth),
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "receipt_expired"

def test_revoked_runtime_authorization_is_blocked():
    auth = _allow()
    assert storage.revoke_receipt(auth["receipt_id"])
    r = client.post(
        "/v1/broker/execute",
        params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
        json=_broker_payload(auth),
    )
    assert r.status_code == 200
    assert r.json()["reason"] == "receipt_revoked"

def test_runtime_authorization_replay_is_blocked(monkeypatch):
    auth = _allow()
    monkeypatch.setattr(broker.httpx, "AsyncClient", FakeAsyncClient)
    params = {"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"}
    first = client.post("/v1/broker/execute", params=params, json=_broker_payload(auth))
    second = client.post("/v1/broker/execute", params=params, json=_broker_payload(auth))
    assert first.status_code == 200
    assert first.json()["executed"] is True
    assert second.status_code == 200
    assert second.json()["reason"] == "receipt_already_consumed"

def test_invalid_runtime_signature_is_blocked():
    auth = _allow()
    stored = storage.get_receipt(auth["receipt_id"])
    stored.signature.value = "tampered"
    original_get = storage.get_receipt
    storage.get_receipt = lambda receipt_id: stored if receipt_id == auth["receipt_id"] else original_get(receipt_id)
    try:
        r = client.post(
            "/v1/broker/execute",
            params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
            json=_broker_payload(auth),
        )
    finally:
        storage.get_receipt = original_get
    assert r.status_code == 200
    assert r.json()["reason"] == "signature_invalid"

def test_kill_switch_blocks_runtime_broker():
    auth = _allow()
    on = client.post(
        "/v1/admin/kill-switch",
        json={"active": True, "reason": "runtime broker test"},
        headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"},
    )
    assert on.status_code == 200
    try:
        r = client.post(
            "/v1/broker/execute",
            params={"receipt_id": auth["receipt_id"], "execution_webhook": "https://example.com/cyraduct-test"},
            json=_broker_payload(auth),
        )
        assert r.status_code == 503
    finally:
        off = client.post(
            "/v1/admin/kill-switch",
            json={"active": False, "reason": None},
            headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"},
        )
        assert off.status_code == 200
