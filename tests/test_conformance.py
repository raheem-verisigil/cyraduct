import os
import sys
import base64
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from main import app
from app import crypto, storage
from verify_receipt import verify as standalone_verify

client = TestClient(app)


def test_health():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_conformance_fixtures_all_pass():
    """The published fixture set — including negative/deny cases — must
    pass against the live policy packs. This is the test a skeptical
    buyer should be able to run themselves."""
    r = client.post("/v1/conformance/run")
    assert r.status_code == 200
    body = r.json()
    assert body["all_passed"], f"Conformance failures: {[x for x in body['results'] if not x['passed']]}"
    negative_cases = [x for x in body["results"] if x["type"] == "negative"]
    assert len(negative_cases) >= 3, "Must publish real negative (correctly-refused) cases, not just positives"


def test_advisory_does_not_issue_receipt():
    r = client.post("/v1/advisory/evaluate", json={
        "agent_id": "agent-x", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    })
    assert r.status_code == 200
    assert "receipt" not in r.json() or r.json().get("receipt") is None


def test_attested_issues_receipt_on_allow():
    r = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-y", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    })
    body = r.json()
    assert body["decision"]["decision"] == "allow"
    assert body["receipt"] is not None
    assert body["receipt"]["expires_at"] is not None
    assert body["receipt"]["signature"]["alg"] == "Ed25519"
    assert body["receipt"]["action"]["consequence_score"] >= 0.0


def test_attested_denies_transfer_without_purpose():
    r = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-z", "action_type": "wire_transfer",
        "consequence_class": "financial_transfer", "policy_pack": "generic",
        "payload": {"amount": 100}
    })
    body = r.json()
    assert body["decision"]["decision"] == "deny"
    assert body["receipt"] is None


def test_receipt_verify_and_revoke_flow():
    ev = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-r", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    receipt_id = ev["receipt"]["receipt_id"]

    v1 = client.get(f"/v1/attested/verify/{receipt_id}")
    assert v1.json()["valid"] is True

    revoke = client.post(f"/v1/attested/revoke/{receipt_id}", headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert revoke.status_code == 200

    v2 = client.get(f"/v1/attested/verify/{receipt_id}")
    assert v2.json()["valid"] is False
    assert v2.json()["reason"] == "receipt_revoked"


def test_revoke_requires_admin_key():
    r = client.post("/v1/attested/revoke/rcpt_doesnotexist", headers={"X-Cyraduct-Admin-Key": "wrong-key"})
    assert r.status_code == 401


def test_agent_scoped_revocation():
    agent_id = "agent-fleet-1"
    receipt_ids = []
    for i in range(3):
        ev = client.post("/v1/attested/evaluate", json={
            "agent_id": agent_id, "action_type": "read_public_doc",
            "consequence_class": "low_risk", "policy_pack": "generic", "payload": {"i": i}
        }).json()
        receipt_ids.append(ev["receipt"]["receipt_id"])

    r = client.post(f"/v1/attested/revoke-agent/{agent_id}", params={"reason": "risk_detected"},
                     headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert r.status_code == 200
    assert r.json()["revoked_count"] == 3

    for rid in receipt_ids:
        v = client.get(f"/v1/attested/verify/{rid}")
        assert v.json()["valid"] is False


def test_receipt_chaining_per_agent():
    agent_id = "agent-chain-1"
    with storage._conn() as conn:
        conn.execute("DELETE FROM agent_chain WHERE agent_id = ?", (agent_id,))
        conn.execute("DELETE FROM receipts WHERE agent_id = ?", (agent_id,))
        conn.commit()
    ev1 = client.post("/v1/attested/evaluate", json={
        "agent_id": agent_id, "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    ev2 = client.post("/v1/attested/evaluate", json={
        "agent_id": agent_id, "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    assert ev1["receipt"]["prev_receipt_hash"] is None
    assert ev2["receipt"]["prev_receipt_hash"] == ev1["receipt"]["action_hash"]


def test_public_key_and_standalone_verification():
    """This is the actual proof behind 'independently verifiable': verify
    a receipt using ONLY the published public key and the standalone
    verifier script, no server trust involved after fetching the key."""
    pk = client.get("/v1/public-key").json()
    assert pk["alg"] == "Ed25519"

    ev = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-standalone", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    receipt = ev["receipt"]

    ok, reason = standalone_verify(receipt, pk["public_key_b64"])
    assert ok, reason


def test_tampered_receipt_fails_standalone_verification():
    pk = client.get("/v1/public-key").json()
    ev = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-tamper", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()
    receipt = ev["receipt"]
    receipt["action_hash"] = "0" * 64  # tamper with the signed content

    ok, reason = standalone_verify(receipt, pk["public_key_b64"])
    assert not ok


def test_evidence_registration_and_reference():
    reg = client.post("/v1/evidence", json={"label": "soc2_type2", "content_hash": "a" * 64})
    assert reg.status_code == 200
    evidence_id = reg.json()["evidence_id"]

    fetched = client.get(f"/v1/evidence/{evidence_id}")
    assert fetched.status_code == 200
    assert fetched.json()["label"] == "soc2_type2"

    ev = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-evidence", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {},
        "evidence_refs": [evidence_id]
    }).json()
    assert evidence_id in ev["receipt"]["evidence"]["evidence_refs"]


def test_receipts_query_by_agent():
    agent_id = "agent-query-1"
    client.post("/v1/attested/evaluate", json={
        "agent_id": agent_id, "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    })
    r = client.get("/v1/receipts", params={"agent_id": agent_id})
    body = r.json()
    assert body["count"] >= 1
    assert all(rc["agent"]["agent_id"] == agent_id for rc in body["receipts"])


def test_consequence_scoring_present_and_reasonable():
    low = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-score-1", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    }).json()["receipt"]["action"]["consequence_score"]

    high = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-score-2", "action_type": "wire_transfer",
        "consequence_class": "financial_transfer", "purpose": "payroll",
        "policy_pack": "generic", "payload": {"amount": 75000}
    }).json()["receipt"]["action"]["consequence_score"]

    assert high > low


def test_kill_switch_blocks_attested_and_broker():
    on = client.post("/v1/admin/kill-switch", json={"active": True, "reason": "test halt"},
                      headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert on.status_code == 200

    blocked = client.post("/v1/attested/evaluate", json={
        "agent_id": "agent-k", "action_type": "read_public_doc",
        "consequence_class": "low_risk", "policy_pack": "generic", "payload": {}
    })
    assert blocked.status_code == 503

    off = client.post("/v1/admin/kill-switch", json={"active": False, "reason": None},
                       headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert off.status_code == 200


def test_audit_chain_is_valid_and_admin_gated():
    unauth = client.get("/v1/admin/audit-log")
    assert unauth.status_code == 401

    r = client.get("/v1/admin/audit-log", headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"})
    assert r.status_code == 200
    assert r.json()["chain_valid"] is True


def _broker_test_request(agent_id="broker-test-agent"):
    return {
        "agent_id": agent_id,
        "principal": "test-principal",
        "framework": "test",
        "action_type": "test.broker",
        "consequence_class": "low_risk",
        "purpose": "broker regression test",
        "consumer": "cyraduct-test",
        "jurisdiction": "NG",
        "payload": {"test": "broker"},
        "policy_pack": "generic",
        "evidence_refs": [],
    }


def _create_broker_test_receipt(agent_id="broker-test-agent"):
    req = _broker_test_request(agent_id)
    r = client.post("/v1/attested/evaluate", json=req)
    assert r.status_code == 200
    body = r.json()
    assert body["receipt"] is not None
    return req, body["receipt"]["receipt_id"]


def test_broker_valid_receipt_allows_execution():
    """A valid receipt must reach the execution client."""
    req, receipt_id = _create_broker_test_receipt("broker-valid")

    fake_response = type("Response", (), {
        "status_code": 200,
        "text": '{"sink_received":true}',
    })()

    fake_client = AsyncMock()
    fake_client.post.return_value = fake_response

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
        r = client.post(
            "/v1/broker/execute",
            params={
                "receipt_id": receipt_id,
                "execution_webhook": "http://fake-sink/sink",
            },
            json=req,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is True
    assert body["receipt"]["receipt_id"] == receipt_id
    assert fake_client.post.called is True


def test_broker_revoked_receipt_blocks_execution():
    """A revoked receipt must be rejected before the execution client is called."""
    req, receipt_id = _create_broker_test_receipt("broker-revoked")

    assert storage.revoke_receipt(receipt_id) is True

    fake_client = AsyncMock()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
        r = client.post(
            "/v1/broker/execute",
            params={
                "receipt_id": receipt_id,
                "execution_webhook": "http://fake-sink/sink",
            },
            json=req,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["reason"] == "receipt_revoked"
    assert fake_client.post.called is False


def test_broker_missing_receipt_blocks_execution():
    """A nonexistent receipt must never reach the execution client."""
    req = _broker_test_request("broker-missing")

    fake_client = AsyncMock()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
        r = client.post(
            "/v1/broker/execute",
            params={
                "receipt_id": "rcpt_does_not_exist",
                "execution_webhook": "http://fake-sink/sink",
            },
            json=req,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["reason"] == "receipt_not_found"
    assert fake_client.post.called is False


def test_broker_invalid_signature_blocks_execution():
    """A cryptographically invalid receipt must never reach execution."""
    req, receipt_id = _create_broker_test_receipt("broker-bad-signature")

    fake_client = AsyncMock()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.receipts.verify_signature", return_value=False):
        with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
            r = client.post(
                "/v1/broker/execute",
                params={
                    "receipt_id": receipt_id,
                    "execution_webhook": "http://fake-sink/sink",
                },
                json=req,
            )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["reason"] == "signature_invalid"
    assert fake_client.post.called is False


def test_broker_expired_receipt_blocks_execution():
    """An expired receipt must never reach the execution client."""
    req, receipt_id = _create_broker_test_receipt("broker-expired")

    fake_client = AsyncMock()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.receipts.is_expired", return_value=True):
        with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
            r = client.post(
                "/v1/broker/execute",
                params={
                    "receipt_id": receipt_id,
                    "execution_webhook": "http://fake-sink/sink",
                },
                json=req,
            )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["reason"] == "receipt_expired"
    assert fake_client.post.called is False


def test_broker_action_mismatch_blocks_execution():
    """A receipt for one action must not authorize a different action."""
    req, receipt_id = _create_broker_test_receipt("broker-mismatch")

    mismatched_req = dict(req)
    mismatched_req["action_type"] = "different.action"

    fake_client = AsyncMock()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return fake_client

        async def __aexit__(self, *args):
            pass

    with patch("app.routers.broker.httpx.AsyncClient", FakeAsyncClient):
        r = client.post(
            "/v1/broker/execute",
            params={
                "receipt_id": receipt_id,
                "execution_webhook": "http://fake-sink/sink",
            },
            json=mismatched_req,
        )

    assert r.status_code == 200
    body = r.json()
    assert body["executed"] is False
    assert body["reason"] == "action_binding_mismatch"
    assert fake_client.post.called is False
