"""Tests for the finance_vendor_change_v1 pack and the generic <field>_missing condition."""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
PACK = "finance_vendor_change_v1"

GOOD_CHANGE = dict(callback_verified=True, callback_channel_preexisting=True, reviewer_id="user_391",
                   new_beneficiary=True, dual_approval=True, sender_domain_match=True,
                   old_account_fingerprint="sha256:aaa", new_account_fingerprint="sha256:bbb")


def change(**over):
    p = {**GOOD_CHANGE, **over}
    p = {k: v for k, v in p.items() if v != "__drop__"}
    return dict(agent_id="test-fin-agent", action_type="update_vendor_bank_details",
                consequence_class="vendor_master_change", purpose="supplier payment-account update",
                jurisdiction="US", policy_pack=PACK, payload=p)


def pay(action="initiate_wire_transfer", **over):
    p = {"amount": 20000, "days_since_bank_change": 90, "dual_approval": True, **over}
    p = {k: v for k, v in p.items() if v != "__drop__"}
    return dict(agent_id="test-fin-agent", action_type=action, consequence_class="financial_transfer",
                purpose="invoice 4471", jurisdiction="US", policy_pack=PACK, payload=p)


def decide(req):
    r = client.post("/v1/attested/evaluate", json=req)
    assert r.status_code == 200
    return r.json()


def test_fully_verified_change_is_allowed_with_receipt():
    b = decide(change())
    assert b["decision"]["decision"] == "allow" and b["receipt"]


def test_receipt_for_vendor_change_is_short_lived():
    r = decide(change())["receipt"]
    from datetime import datetime
    secs = (datetime.fromisoformat(r["expires_at"]) - datetime.fromisoformat(r["issued_at"])).total_seconds()
    assert 800 <= secs <= 1000


def test_missing_callback_fact_fails_closed():
    b = decide(change(callback_verified="__drop__"))
    assert b["decision"]["decision"] == "deny" and b["receipt"] is None
    assert "fin.vendor.deny.callback_not_supplied" in b["decision"]["matched_rules"]


def test_callback_false_denied():
    assert decide(change(callback_verified=False))["decision"]["decision"] == "deny"


def test_callback_to_number_from_the_request_denied():
    b = decide(change(callback_channel_preexisting=False))
    assert "fin.vendor.deny.callback_channel_from_request" in b["decision"]["matched_rules"]


def test_every_required_vendor_fact_fails_closed_when_absent():
    for f in ("callback_channel_preexisting", "reviewer_id", "new_beneficiary", "sender_domain_match"):
        b = decide(change(**{f: "__drop__"}))
        assert b["decision"]["decision"] == "deny", f"{f} missing must deny"


def test_new_beneficiary_needs_dual_approval():
    assert decide(change(dual_approval=False))["decision"]["decision"] == "deny"
    assert decide(change(dual_approval="__drop__"))["decision"]["decision"] == "deny"


def test_sender_domain_mismatch_is_conditional_not_allow():
    b = decide(change(sender_domain_match=False))
    assert b["decision"]["decision"] == "conditional"


def test_bec_shape_is_denied():
    b = decide(change(callback_channel_preexisting=False, sender_domain_match=False, dual_approval=False))
    assert b["decision"]["decision"] == "deny" and b["receipt"] is None


def test_normal_wire_allowed_and_big_wire_needs_dual_approval():
    assert decide(pay())["decision"]["decision"] == "allow"
    assert decide(pay(amount=150000))["decision"]["decision"] == "allow"
    assert decide(pay(amount=150000, dual_approval=False))["decision"]["decision"] == "deny"
    assert decide(pay(amount=150000, dual_approval="__drop__"))["decision"]["decision"] == "deny"
    assert decide(pay(amount=6000000))["decision"]["decision"] == "deny"


def test_payment_after_recent_bank_change_is_held():
    assert decide(pay(days_since_bank_change=1))["decision"]["decision"] == "conditional"


def test_payment_without_bank_change_age_fails_closed():
    assert decide(pay(days_since_bank_change="__drop__"))["decision"]["decision"] == "deny"


def test_large_ach_conditional():
    assert decide(pay("initiate_ach_payment", amount=300000))["decision"]["decision"] == "conditional"


def test_vendor_change_without_amount_is_not_rejected_as_financial_transfer():
    """financial_transfer requires a numeric amount; vendor changes use their own class."""
    b = decide(change())
    assert "amount_must_be_numeric" not in " ".join(b["decision"]["reasons"])


def test_financial_transfer_class_still_requires_amount_for_vendor_style_payload():
    req = change()
    req["consequence_class"] = "financial_transfer"
    b = decide(req)
    assert b["decision"]["decision"] == "deny"
    assert "financial_transfer_amount_must_be_numeric" in b["decision"]["reasons"]


def test_generic_missing_condition_does_not_change_existing_packs():
    r = client.post("/v1/attested/evaluate", json=dict(
        agent_id="test-a", action_type="wire_transfer", consequence_class="financial_transfer",
        purpose="payroll", policy_pack="generic", payload={"amount": 75000}))
    assert r.json()["decision"]["decision"] == "conditional"
