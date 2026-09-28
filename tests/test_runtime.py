from fastapi.testclient import TestClient

import pytest
from main import app
from app.storage import get_kill_switch, set_kill_switch


@pytest.fixture(autouse=True)
def isolate_kill_switch():
    previous = get_kill_switch()
    set_kill_switch(False, None)
    yield
    set_kill_switch(previous["active"], previous["reason"])


client = TestClient(app)


def _request(**overrides):
    body = {
        "agent_id": "runtime-test-agent",
        "action_type": "update_customer_record",
        "consequence_class": "generic_tool_call",
        "target": "crm",
        "resource": "customer/123",
        "reversibility": "reversible",
        "authority": "present",
        "policy_pack": "generic",
        "payload": {},
        "runtime_state": {},
    }
    body.update(overrides)
    return body


def test_runtime_allows_normal_action():
    r = client.post("/v1/runtime/evaluate", json=_request())
    assert r.status_code == 200
    assert r.json()["decision"] == "allow"


def test_runtime_holds_missing_authority():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(authority="missing"),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "hold"


def test_runtime_reauthorizes_when_state_changed():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(
            authorized_state_version="42",
            current_state_version="43",
        ),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "reauthorize"


def test_runtime_reauthorizes_expired_authorization():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(
            authorization_expires_at="2020-01-01T00:00:00+00:00",
        ),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "reauthorize"


def test_runtime_throttles_high_action_velocity():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(runtime_state={"actions_last_minute": 61}),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "throttle"


def test_runtime_holds_delegated_irreversible_action():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(
            consequence_class="infra_change",
            authority="delegated",
            reversibility="irreversible",
        ),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "hold"


def test_runtime_denies_unknown_consequence_class():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(consequence_class="not_a_real_class"),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "deny"


def test_runtime_denies_malformed_runtime_signal():
    r = client.post(
        "/v1/runtime/evaluate",
        json=_request(runtime_state={"actions_last_minute": -1}),
    )
    assert r.status_code == 200
    assert r.json()["decision"] == "deny"


def test_runtime_kill_switch_blocks_evaluation():
    on = client.post(
        "/v1/admin/kill-switch",
        json={"active": True, "reason": "runtime test"},
        headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"},
    )
    assert on.status_code == 200

    blocked = client.post("/v1/runtime/evaluate", json=_request())
    assert blocked.status_code == 503

    off = client.post(
        "/v1/admin/kill-switch",
        json={"active": False, "reason": None},
        headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"},
    )
    assert off.status_code == 200
