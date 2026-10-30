import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

"""NCS pilot tests for Cyraduct Finance Guard policy-delta behaviour.

These tests measure application policy outcomes, not an AI model's native conduct.
All identifiers and vendor/payment facts are synthetic.
"""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def vendor_change_payload(**overrides):
    payload = {
        "callback_verified": True,
        "callback_channel_preexisting": True,
        "reviewer_id": "test-reviewer-01",
        "new_beneficiary": False,
        "dual_approval": False,
        "sender_domain_match": True,
        "vendor_id": "synthetic-vendor-001",
        "old_account_fingerprint": "sha256:" + "1" * 64,
        "new_account_fingerprint": "sha256:" + "2" * 64,
    }
    payload.update(overrides)
    return payload


def evaluate(agent_suffix, consequence_class, action_type, payload, purpose=None):
    request = {
        "agent_id": f"test-ncs-{agent_suffix}",
        "action_type": action_type,
        "consequence_class": consequence_class,
        "purpose": purpose,
        "consumer": "synthetic-erp:payables",
        "jurisdiction": "NG",
        "policy_pack": "finance_vendor_change_v1",
        "payload": payload,
    }
    response = client.post("/v1/attested/evaluate", json=request)
    assert response.status_code == 200, response.text
    return response.json()


def test_ncs_valid_vendor_change_issues_signed_receipt():
    result = evaluate(
        "valid-vendor", "vendor_master_change",
        "update_vendor_bank_details", vendor_change_payload(),
        "synthetic supplier account update",
    )
    assert result["decision"]["decision"] == "allow"
    assert result["receipt"] is not None
    assert result["receipt"]["signature"]["alg"] == "Ed25519"
    assert result["receipt"]["policy"]["policy_pack"] == "finance_vendor_change_v1"


def test_ncs_missing_callback_evidence_denies_without_receipt():
    payload = vendor_change_payload()
    payload.pop("callback_verified")
    result = evaluate("missing-callback", "vendor_master_change",
                      "update_vendor_bank_details", payload, "synthetic update")
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_requester_supplied_callback_channel_is_denied():
    result = evaluate("untrusted-channel", "vendor_master_change",
                      "update_vendor_bank_details",
                      vendor_change_payload(callback_channel_preexisting=False),
                      "synthetic update")
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_missing_reviewer_is_denied():
    payload = vendor_change_payload()
    payload.pop("reviewer_id")
    result = evaluate("missing-reviewer", "vendor_master_change",
                      "update_vendor_bank_details", payload, "synthetic update")
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_new_beneficiary_without_dual_approval_is_denied():
    result = evaluate("no-dual-approval", "vendor_master_change",
                      "update_vendor_bank_details",
                      vendor_change_payload(new_beneficiary=True, dual_approval=False),
                      "synthetic update")
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_financial_transfer_without_purpose_is_denied():
    result = evaluate("no-purpose", "financial_transfer",
                      "initiate_wire_transfer",
                      {"amount": 25000, "days_since_bank_change": 10})
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_recent_bank_change_escalates_to_conditional():
    result = evaluate("recent-change", "financial_transfer",
                      "initiate_wire_transfer",
                      {"amount": 25000, "days_since_bank_change": 1,
                       "dual_approval": True},
                      "synthetic supplier invoice")
    assert result["decision"]["decision"] == "conditional"
    assert result["receipt"] is not None



def test_ncs_wire_above_policy_ceiling_is_denied():
    result = evaluate(
        "wire-over-ceiling", "financial_transfer",
        "initiate_wire_transfer",
        {"amount": 5000001, "days_since_bank_change": 10, "dual_approval": True},
        "synthetic payroll",
    )
    assert result["decision"]["decision"] == "deny"
    assert result["receipt"] is None


def test_ncs_receipt_revocation_is_visible_to_attested_verifier():
    result = evaluate(
        "revocation", "low_risk", "read_public_doc", {},
        "synthetic revocation test",
    )
    receipt_id = result["receipt"]["receipt_id"]
    revoked = client.post(
        f"/v1/attested/revoke/{receipt_id}",
        headers={"X-Cyraduct-Admin-Key": "dev-insecure-admin-key"},
    )
    assert revoked.status_code == 200
    verification = client.get(f"/v1/attested/verify/{receipt_id}")
    assert verification.status_code == 200
    assert verification.json()["valid"] is False
    assert verification.json()["reason"] == "receipt_revoked"
