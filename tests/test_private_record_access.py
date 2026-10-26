"""Access-control regression tests for private evidence and receipt records."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app
from app import config, storage

client = TestClient(app)
ADMIN = {"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"}
TEST_KEY = "test-key-for-pytest-only"
config.TEST_ADMIN_KEY = TEST_KEY
TEST = {"X-Cyraduct-Admin-Key": TEST_KEY}


def _issue_receipt(agent_id: str) -> str:
    response = client.post("/v1/attested/evaluate", json={
        "agent_id": agent_id,
        "action_type": "read_public_doc",
        "consequence_class": "low_risk",
        "policy_pack": "generic",
        "payload": {},
    })
    assert response.status_code == 200
    assert response.json()["receipt"] is not None
    return response.json()["receipt"]["receipt_id"]


def test_evidence_registry_requires_full_admin_key():
    payload = {"label": "private-test", "content_hash": "a" * 64}
    assert client.post("/v1/evidence", json=payload).status_code == 401
    assert client.post("/v1/evidence", json=payload, headers=TEST).status_code == 403

    created = client.post("/v1/evidence", json=payload, headers=ADMIN)
    assert created.status_code == 200
    evidence_id = created.json()["evidence_id"]
    assert client.get(f"/v1/evidence/{evidence_id}").status_code == 401
    assert client.get(f"/v1/evidence/{evidence_id}", headers=TEST).status_code == 403
    fetched = client.get(f"/v1/evidence/{evidence_id}", headers=ADMIN)
    assert fetched.status_code == 200
    assert fetched.json()["evidence_id"] == evidence_id


def test_receipt_queries_require_authentication():
    receipt_id = _issue_receipt("private-record-real-agent")
    assert client.get("/v1/receipts").status_code == 401
    assert client.get(f"/v1/receipts/{receipt_id}").status_code == 401
    assert client.get("/v1/receipts", headers=ADMIN).status_code == 200
    assert client.get(f"/v1/receipts/{receipt_id}", headers=ADMIN).status_code == 200


def test_test_key_receipt_query_is_limited_to_test_namespace():
    test_id = _issue_receipt("test-private-record-agent")
    real_id = _issue_receipt("private-record-real-agent-2")

    assert client.get("/v1/receipts", headers=TEST).status_code == 403
    assert client.get("/v1/receipts", params={"agent_id": "private-record-real-agent-2"}, headers=TEST).status_code == 403

    response = client.get("/v1/receipts", params={"agent_id": "test-private-record-agent"}, headers=TEST)
    assert response.status_code == 200
    returned_ids = {r["receipt_id"] for r in response.json()["receipts"]}
    assert test_id in returned_ids
    assert real_id not in returned_ids

    assert client.get(f"/v1/receipts/{test_id}", headers=TEST).status_code == 200
    assert client.get(f"/v1/receipts/{real_id}", headers=TEST).status_code == 404


def test_kill_switch_status_requires_full_admin_key():
    assert client.get("/v1/admin/kill-switch").status_code == 401
    assert client.get("/v1/admin/kill-switch", headers=TEST).status_code == 403
    assert client.get("/v1/admin/kill-switch", headers=ADMIN).status_code == 200
