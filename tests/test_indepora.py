import base64
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.canonical import action_hash, sha256_hex
from app.indepora import verify_and_bind
from app.models import ActionRequest
from app import policy_engine
from main import app

client = TestClient(app)


def key_material():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private, base64.b64encode(public).decode()


def record(private, *, valid_until=None, standing="sufficient", unknown=0, origins=3):
    payload = {
        "schema": "indepora.evidence_continuity_record.v1",
        "record_id": "icr-test-001",
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "valid_until": valid_until or (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        "origin_assessment": {
            "candidate_origin_count": origins,
            "unknown_relationship_count": unknown,
            "conflict_count": 0,
            "independence_status": standing,
        },
        "standing": {"status": standing},
        "continuity": {"record_sequence": 1, "superseded": False},
    }
    record_hash = sha256_hex(payload)
    signature = base64.b64encode(private.sign(record_hash.encode("ascii"))).decode()
    return {
        **payload,
        "record_hash": record_hash,
        "signature": {"algorithm": "Ed25519", "key_id": "indepora-test-1", "value": signature},
    }


def request(**overrides):
    values = {
        "agent_id": "agent-indepora-test",
        "principal": "org:test",
        "action_type": "update_vendor_bank_details",
        "consequence_class": "vendor_master_change",
        "purpose": "test evidence binding",
        "policy_pack": "generic",
        "payload": {"vendor_id": "vendor-a"},
    }
    values.update(overrides)
    return ActionRequest(**values)


def test_continuity_record_verifies_to_allowlisted_binding():
    private, public = key_material()
    verified = verify_and_bind(record(private), public_key_b64=public, expected_key_id="indepora-test-1")
    assert verified.record_id == "icr-test-001"
    assert verified.candidate_origin_count == 3
    assert verified.unknown_relationship_count == 0
    assert verified.not_superseded is True


def test_continuity_record_mutation_and_expiry_fail_closed():
    private, public = key_material()
    mutated = record(private)
    mutated["origin_assessment"]["candidate_origin_count"] = 8
    try:
        verify_and_bind(mutated, public_key_b64=public, expected_key_id="indepora-test-1")
        assert False, "mutated record must be rejected"
    except ValueError as exc:
        assert str(exc) == "indepora_record_hash_mismatch"

    expired = record(private, valid_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    try:
        verify_and_bind(expired, public_key_b64=public, expected_key_id="indepora-test-1")
        assert False, "expired record must be rejected"
    except ValueError as exc:
        assert str(exc) == "indepora_record_expired"


def test_policy_evaluation_derives_binding_and_hash_changes(monkeypatch):
    private, public = key_material()
    monkeypatch.setenv("INDEPORA_PUBLIC_KEY_B64", public)
    monkeypatch.setenv("INDEPORA_KEY_ID", "indepora-test-1")
    signed = record(private)
    req = request(indepora_record=signed)
    decision = policy_engine.evaluate(req)
    assert decision.decision == "allow"
    assert req.evidence_assurance is not None
    assert action_hash(req, "act-1") != action_hash(request(), "act-1")


def test_agent_cannot_supply_binding_without_signed_record():
    req = request(evidence_assurance={
        "record_id": "fake",
        "record_hash": "sha256:fake",
        "standing": "sufficient",
        "candidate_origin_count": 8,
        "unknown_relationship_count": 0,
        "conflict_count": 0,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "valid_until": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "verification_key_id": "fake",
    })
    assert policy_engine.evaluate(req).reasons == ["indepora_binding_requires_signed_record"]


def test_indepora_verify_endpoint_returns_trusted_binding(monkeypatch):
    private, public = key_material()
    monkeypatch.setenv("INDEPORA_PUBLIC_KEY_B64", public)
    monkeypatch.setenv("INDEPORA_KEY_ID", "indepora-test-1")
    response = client.post("/v1/indepora/verify", json=record(private))
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["binding"]["record_id"] == "icr-test-001"


def test_broker_rechecks_record_before_execution(monkeypatch):
    private, public = key_material()
    monkeypatch.setenv("INDEPORA_PUBLIC_KEY_B64", public)
    monkeypatch.setenv("INDEPORA_KEY_ID", "indepora-test-1")
    signed = record(private)
    req = request(indepora_record=signed)
    evaluated = client.post("/v1/attested/evaluate", json=req.model_dump()).json()
    assert evaluated["receipt"]["evidence_assurance"]["record_id"] == "icr-test-001"

    tampered = dict(signed)
    tampered["origin_assessment"] = dict(signed["origin_assessment"], candidate_origin_count=8)
    altered = req.model_copy(update={"indepora_record": tampered})
    response = client.post(
        "/v1/broker/execute",
        params={"receipt_id": evaluated["receipt"]["receipt_id"], "execution_webhook": "https://example.invalid/sink"},
        json=altered.model_dump(),
    )
    assert response.json()["executed"] is False
    assert response.json()["reason"] == "indepora_record_hash_mismatch"
