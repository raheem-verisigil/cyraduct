"""
Regression tests for the action-hash field-binding gap found by external
adversarial review (credited: Jake Macdonald, frozen-specimen test on
Cyraduct's live API).

Original finding: purpose, jurisdiction, and policy_pack could all
participate in the policy decision at issuance without being part of
what the receipt's action_hash (and therefore its Ed25519 signature)
actually bound. A receipt issued partly on the strength of a stated
purpose could be presented at broker execution time with a DIFFERENT
purpose and still pass verify_action_binding(), because purpose was
never in the hashed/signed content.

These tests reproduce that exact finding against the pre-fix behavior
description, and confirm the fix closes it.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import ActionRequest
from app.receipts import _action_hash, verify_action_binding, issue_receipt


def _base_request(**overrides) -> ActionRequest:
    defaults = dict(
        agent_id="test-jake-repro",
        action_type="wire_transfer",
        consequence_class="financial_transfer",
        purpose="vendor settlement",
        jurisdiction="US",
        policy_pack="generic",
        payload={"amount": 75000},
    )
    defaults.update(overrides)
    return ActionRequest(**defaults)


def test_changing_purpose_now_changes_the_action_hash():
    """This is Jake's exact reproduction: 'changing only the purpose left
    the action hash unchanged.' Confirms that's no longer true."""
    req_a = _base_request(purpose="vendor settlement")
    req_b = _base_request(purpose="emergency payroll")

    hash_a = _action_hash(req_a, "act_fixed_id")
    hash_b = _action_hash(req_b, "act_fixed_id")

    assert hash_a != hash_b, "purpose change must change the action hash (this was the reported gap)"


def test_changing_jurisdiction_now_changes_the_action_hash():
    """Same class of bug as purpose — jurisdiction also participates in
    policy decisions (jurisdiction_in / jurisdiction_missing conditions)
    and had the identical gap."""
    req_a = _base_request(jurisdiction="US")
    req_b = _base_request(jurisdiction="EU")

    hash_a = _action_hash(req_a, "act_fixed_id")
    hash_b = _action_hash(req_b, "act_fixed_id")

    assert hash_a != hash_b, "jurisdiction change must change the action hash"


def test_changing_policy_pack_now_changes_the_action_hash():
    req_a = _base_request(policy_pack="generic")
    req_b = _base_request(policy_pack="banking")

    hash_a = _action_hash(req_a, "act_fixed_id")
    hash_b = _action_hash(req_b, "act_fixed_id")

    assert hash_a != hash_b, "policy_pack change must change the action hash"


def test_amount_change_still_changes_the_hash_as_before():
    """Confirms the fix didn't regress the part that already worked —
    Jake's report explicitly noted 'changing the transfer amount changed
    the hash,' i.e. payload was already correctly bound."""
    req_a = _base_request(payload={"amount": 75000})
    req_b = _base_request(payload={"amount": 999999})

    hash_a = _action_hash(req_a, "act_fixed_id")
    hash_b = _action_hash(req_b, "act_fixed_id")

    assert hash_a != hash_b


def test_verify_action_binding_rejects_purpose_swap_post_issuance():
    """End-to-end version of the finding: issue a receipt with one
    purpose, then present it at 'execution time' with a different
    purpose but everything else identical. Must be rejected."""
    original_req = _base_request(purpose="vendor settlement")
    receipt = issue_receipt(
        original_req, action_id="act_binding_test", decision="conditional",
        policy_pack="generic", policy_pack_version="0.1.0",
        matched_rules=["generic.conditional.financial_transfer.review_band"],
        reasons=["review band"],
    )

    swapped_purpose_req = _base_request(purpose="emergency payroll")  # only purpose differs
    assert verify_action_binding(receipt, swapped_purpose_req) is False

    # Sanity: the original, unmodified request still binds correctly.
    assert verify_action_binding(receipt, original_req) is True


def test_verify_action_binding_rejects_jurisdiction_swap_post_issuance():
    original_req = _base_request(jurisdiction="US")
    receipt = issue_receipt(
        original_req, action_id="act_binding_test_2", decision="allow",
        policy_pack="generic", policy_pack_version="0.1.0",
        matched_rules=[], reasons=[],
    )

    swapped_req = _base_request(jurisdiction="EU")
    assert verify_action_binding(receipt, swapped_req) is False
    assert verify_action_binding(receipt, original_req) is True


def test_verify_action_binding_rejects_policy_pack_swap_post_issuance():
    original_req = _base_request(policy_pack="generic")
    receipt = issue_receipt(
        original_req, action_id="act_binding_test_3", decision="allow",
        policy_pack="generic", policy_pack_version="0.1.0",
        matched_rules=[], reasons=[],
    )

    swapped_req = _base_request(policy_pack="banking")
    assert verify_action_binding(receipt, swapped_req) is False
