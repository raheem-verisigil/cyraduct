"""
Tenant isolation.

Proves that a receipt issued to one tenant cannot be seen, verified,
executed, revoked or listed by another tenant (or by an unauthenticated
caller), that per-agent hash chains are separate per tenant, that API keys
are stored hashed, and that CYRADUCT_REQUIRE_TENANT_AUTH turns key-less
access to evaluate/broker into a 401 while leaving admin access intact.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from app import config, storage

client = TestClient(app)
ADMIN = {"X-Cyraduct-Admin-Key": config.ADMIN_API_KEY}


@pytest.fixture(autouse=True)
def _reset_limiter():
    app.state.limiter.reset()
    yield
    app.state.limiter.reset()


def _tenant(name):
    r = client.post("/v1/admin/tenants", json={"name": name}, headers=ADMIN)
    assert r.status_code == 200, r.text
    body = r.json()
    return body["tenant_id"], {"X-Cyraduct-Api-Key": body["api_key"]}


def _action(agent_id):
    return {"agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}}


def _issue(headers, agent_id):
    r = client.post("/v1/attested/evaluate", json=_action(agent_id), headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["receipt"]


def _execute(headers, receipt_id, agent_id):
    # An unsafe webhook means a request that passes the ownership check stops
    # at "unsafe_execution_webhook" without any network access.
    return client.post(
        "/v1/broker/execute",
        params={"receipt_id": receipt_id, "execution_webhook": "https://localhost/sink"},
        json={**_action(agent_id), "action_type": "read_public_doc"},
        headers=headers,
    ).json()


def test_tenant_admin_endpoints_need_full_admin():
    assert client.post("/v1/admin/tenants", json={"name": "x"}).status_code == 401
    assert client.get("/v1/admin/tenants").status_code == 401
    if config.TEST_ADMIN_KEY:
        r = client.post("/v1/admin/tenants", json={"name": "x"},
                        headers={"X-Cyraduct-Admin-Key": config.TEST_ADMIN_KEY})
        assert r.status_code == 403


def test_api_key_is_returned_once_and_stored_hashed():
    tenant_id, hdr = _tenant("hash-check")
    key = hdr["X-Cyraduct-Api-Key"]
    listing = client.get("/v1/admin/tenants", headers=ADMIN).json()["tenants"]
    assert any(t["tenant_id"] == tenant_id for t in listing)
    assert key not in str(listing)
    with storage._engine.begin() as conn:
        stored = conn.execute(select(storage.tenants_table.c.key_hash)
                              .where(storage.tenants_table.c.tenant_id == tenant_id)).scalar()
    assert stored and stored != key and key not in stored


def test_invalid_api_key_is_401_even_when_auth_not_required():
    r = client.post("/v1/attested/evaluate", json=_action("t-bad-key"),
                    headers={"X-Cyraduct-Api-Key": "cyr_not_a_real_key"})
    assert r.status_code == 401


def test_other_tenant_cannot_verify_execute_or_read_a_receipt():
    _, a = _tenant("A-verify")
    _, b = _tenant("B-verify")
    rid = _issue(a, "shared-agent-1")["receipt_id"]

    assert client.get(f"/v1/attested/verify/{rid}", headers=a).json()["valid"] is True
    for hdr in (b, {}):
        v = client.get(f"/v1/attested/verify/{rid}", headers=hdr).json()
        assert v["valid"] is False and v["reason"] == "receipt_not_found"
        assert _execute(hdr, rid, "shared-agent-1")["reason"] == "receipt_not_found"

    assert client.get(f"/v1/receipts/{rid}", headers=b).status_code == 404
    assert client.get(f"/v1/receipts/{rid}", headers=a).status_code == 200

    # The owner passes the ownership check and is stopped by the unsafe webhook.
    assert _execute(a, rid, "shared-agent-1")["reason"].startswith("unsafe_execution_webhook")


def test_other_tenant_cannot_revoke_receipt_or_agent():
    _, a = _tenant("A-revoke")
    _, b = _tenant("B-revoke")
    rid = _issue(a, "shared-agent-2")["receipt_id"]

    assert client.post(f"/v1/attested/revoke/{rid}", headers=b).status_code == 401
    assert client.get(f"/v1/attested/verify/{rid}", headers=a).json()["valid"] is True

    r = client.post("/v1/attested/revoke-agent/shared-agent-2", headers=b)
    assert r.status_code == 200 and r.json()["revoked_count"] == 0
    assert client.get(f"/v1/attested/verify/{rid}", headers=a).json()["valid"] is True

    assert client.post(f"/v1/attested/revoke/{rid}", headers=a).status_code == 200
    assert client.get(f"/v1/attested/verify/{rid}", headers=a).json()["reason"] == "receipt_revoked"


def test_receipt_listing_is_scoped_to_the_tenant():
    _, a = _tenant("A-list")
    _, b = _tenant("B-list")
    ra = _issue(a, "shared-agent-3")["receipt_id"]
    rb = _issue(b, "shared-agent-3")["receipt_id"]

    la = client.get("/v1/receipts", params={"agent_id": "shared-agent-3"}, headers=a).json()
    ids = {r["receipt_id"] for r in la["receipts"]}
    assert ra in ids and rb not in ids


def test_agent_hash_chains_are_separate_per_tenant():
    _, a = _tenant("A-chain")
    _, b = _tenant("B-chain")
    first_a = _issue(a, "shared-agent-4")
    first_b = _issue(b, "shared-agent-4")
    assert first_a["prev_receipt_hash"] is None
    assert first_b["prev_receipt_hash"] is None  # B does not inherit A's chain

    second_a = _issue(a, "shared-agent-4")
    assert second_a["prev_receipt_hash"] == first_a["action_hash"]


def test_legacy_receipts_are_not_usable_by_tenants_and_vice_versa():
    _, a = _tenant("A-legacy")
    legacy = _issue({}, "legacy-agent-1")["receipt_id"]
    assert _execute(a, legacy, "legacy-agent-1")["reason"] == "receipt_not_found"
    assert client.get(f"/v1/attested/verify/{legacy}").json()["valid"] is True


def test_revoking_a_tenant_disables_key_and_revokes_its_receipts():
    tenant_id, a = _tenant("A-offboard")
    rid = _issue(a, "offboard-agent")["receipt_id"]
    assert client.post(f"/v1/admin/tenants/{tenant_id}/revoke", headers=ADMIN).status_code == 200
    assert client.post("/v1/attested/evaluate", json=_action("offboard-agent"), headers=a).status_code == 401
    assert storage.get_receipt(rid).revoked is True
    assert client.post("/v1/admin/tenants/tnt_missing/revoke", headers=ADMIN).status_code == 404


def test_require_tenant_auth_flag_blocks_keyless_calls(monkeypatch):
    _, a = _tenant("A-required")
    monkeypatch.setattr(config, "REQUIRE_TENANT_AUTH", True)

    for path in ("/v1/attested/evaluate", "/v1/advisory/evaluate", "/v1/runtime/evaluate"):
        assert client.post(path, json=_action("req-agent")).status_code == 401, path
    assert client.post("/v1/broker/execute",
                       params={"receipt_id": "rcpt_x", "execution_webhook": "https://localhost/s"},
                       json=_action("req-agent")).status_code == 401

    assert client.post("/v1/attested/evaluate", json=_action("req-agent"), headers=a).status_code == 200
    assert client.post("/v1/advisory/evaluate", json=_action("req-agent"), headers=a).status_code == 200
    # Admin read access is unaffected by the flag.
    assert client.get("/v1/receipts", headers=ADMIN).status_code == 200
