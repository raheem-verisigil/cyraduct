"""
Tests for the scoped test-key authorization model (app/auth.py).

These specifically prove the security property that matters: a test key
can act within the test namespace, and is refused everywhere else —
especially the kill switch, which it must NEVER be able to reach.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from app import config

# Config reads env vars at first import, which may already have happened
# via another test file's `from main import app` before this file loads.
# Patch the module attribute directly instead, so this works regardless
# of pytest's test collection order.
config.TEST_ADMIN_KEY = "test-key-for-pytest-only"

client = TestClient(app)

FULL_ADMIN_KEY = "dev-insecure-admin-key"
TEST_KEY = "test-key-for-pytest-only"


def _issue_receipt(agent_id: str) -> str:
    r = client.post("/v1/attested/evaluate", json={
        "agent_id": agent_id, "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    })
    return r.json()["receipt"]["receipt_id"]


def test_test_key_can_revoke_test_namespaced_receipt():
    receipt_id = _issue_receipt("test-harness-agent-1")
    r = client.post(f"/v1/attested/revoke/{receipt_id}", headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 200
    assert r.json()["revoked"] is True


def test_test_key_cannot_revoke_non_test_namespaced_receipt():
    receipt_id = _issue_receipt("real-customer-agent-1")
    r = client.post(f"/v1/attested/revoke/{receipt_id}", headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 403


def test_test_key_can_revoke_agent_in_test_namespace():
    _issue_receipt("test-fleet-agent-1")
    r = client.post("/v1/attested/revoke-agent/test-fleet-agent-1", headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 200


def test_test_key_cannot_revoke_agent_outside_test_namespace():
    _issue_receipt("real-fleet-agent-1")
    r = client.post("/v1/attested/revoke-agent/real-fleet-agent-1", headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 403


def test_test_key_can_never_reach_kill_switch():
    """The single most important test in this file: a test key must be
    refused here under all circumstances, since the kill switch halts the
    live service for every real caller and there is no staging environment
    to safely delegate this to."""
    r = client.post("/v1/admin/kill-switch", json={"active": True, "reason": "should never work"},
                     headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 403

    # Confirm it genuinely didn't toggle
    status = client.get("/v1/admin/kill-switch").json()
    assert status["active"] is False


def test_full_admin_key_still_has_unrestricted_access():
    """Confirm the scoping addition didn't accidentally weaken the real
    admin key's existing unrestricted access."""
    receipt_id = _issue_receipt("any-agent-full-admin-test")
    r = client.post(f"/v1/attested/revoke/{receipt_id}", headers={"X-Cyraduct-Admin-Key": FULL_ADMIN_KEY})
    assert r.status_code == 200

    on = client.post("/v1/admin/kill-switch", json={"active": True, "reason": "full admin test"},
                      headers={"X-Cyraduct-Admin-Key": FULL_ADMIN_KEY})
    assert on.status_code == 200
    off = client.post("/v1/admin/kill-switch", json={"active": False, "reason": None},
                       headers={"X-Cyraduct-Admin-Key": FULL_ADMIN_KEY})
    assert off.status_code == 200


def test_audit_log_filtered_for_test_key():
    _issue_receipt("test-audit-agent-1")
    r = client.get("/v1/admin/audit-log", headers={"X-Cyraduct-Admin-Key": TEST_KEY})
    assert r.status_code == 200
    body = r.json()
    # Every entry returned must be in the test namespace
    for entry in body["entries"]:
        import json as _json
        detail = _json.loads(entry["detail"])
        if "agent_id" in detail:
            assert detail["agent_id"].startswith("test-")


def test_invalid_key_rejected_everywhere():
    r1 = client.post("/v1/admin/kill-switch", json={"active": True, "reason": "x"},
                      headers={"X-Cyraduct-Admin-Key": "not-a-real-key"})
    assert r1.status_code == 401

    receipt_id = _issue_receipt("test-invalid-key-agent")
    r2 = client.post(f"/v1/attested/revoke/{receipt_id}", headers={"X-Cyraduct-Admin-Key": "not-a-real-key"})
    assert r2.status_code == 401
