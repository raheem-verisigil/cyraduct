"""Focused adversarial tests for immutable receipt-claim integrity."""
import copy

from app import crypto
from app.models import ActionRequest
from app.receipts import issue_receipt, verify_signature
from verify_receipt import verify as standalone_verify


def make_receipt():
    req = ActionRequest(
        agent_id="adversarial-agent",
        principal="org:pilot:finance",
        framework="test-harness",
        action_type="change_vendor_bank_details",
        consequence_class="financial_transfer",
        purpose="verified supplier maintenance",
        jurisdiction="NG",
        policy_pack="finance_guard",
        evidence_refs=["vendor-check-001"],
        payload={"vendor_id": "vendor-001", "account_fingerprint": "sha256:abc123"},
    )
    return issue_receipt(
        req, action_id="action-001", decision="conditional",
        policy_pack="finance_guard", policy_pack_version="1.2.0",
        matched_rules=["finance.vendor_change.requires_human_review"],
        reasons=["human approval required"],
        prev_receipt_hash="sha256:prior-receipt",
    )


def test_server_and_independent_verifier_accept_unmodified_receipt():
    receipt = make_receipt()
    assert verify_signature(receipt)
    valid, reason = standalone_verify(receipt.model_dump(mode="json"), crypto.public_key_b64())
    assert valid, reason


def test_decision_flip_conditional_to_allow_is_rejected():
    receipt = make_receipt()
    receipt.decision = "allow"
    assert not verify_signature(receipt)
    valid, _ = standalone_verify(receipt.model_dump(mode="json"), crypto.public_key_b64())
    assert not valid


def test_mutating_any_critical_signed_claim_is_rejected():
    mutations = [
        lambda r: setattr(r.agent, "agent_id", "attacker-agent"),
        lambda r: setattr(r.action, "type", "initiate_wire_transfer"),
        lambda r: setattr(r.policy, "policy_pack_version", "99.0.0"),
        lambda r: setattr(r.policy, "matched_rules", ["attacker.allow-all"]),
        lambda r: setattr(r.evidence, "evidence_refs", ["fake-evidence"]),
        lambda r: setattr(r, "expires_at", "2099-01-01T00:00:00+00:00"),
        lambda r: setattr(r, "prev_receipt_hash", "attacker-chain-root"),
        lambda r: setattr(r.signature, "key_id", "attacker-key"),
    ]
    original = make_receipt()
    for mutate in mutations:
        candidate = copy.deepcopy(original)
        mutate(candidate)
        assert not verify_signature(candidate), f"mutation survived: {mutate}"


def test_mutable_revocation_and_consumption_state_are_not_signature_inputs():
    receipt = make_receipt()
    receipt.revoked = True
    receipt.consumed_at = "2026-10-26T12:00:00+00:00"
    # These are lifecycle controls evaluated separately from signature integrity.
    assert verify_signature(receipt)
