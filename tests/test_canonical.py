from app.canonical import action_envelope, action_hash, canonical_json_bytes, parameters_hash
from app.models import ActionRequest


def request(**overrides):
    values = {
        "protocol_version": "1.0",
        "request_id": "req-canonical-1",
        "agent_id": "agent-1",
        "principal": "org:acme:finance",
        "framework": "custom",
        "action_type": "update_vendor_bank_details",
        "consequence_class": "vendor_master_change",
        "purpose": "supplier payment-account update",
        "consumer": "erp:acme-payables",
        "jurisdiction": "US",
        "payload": {
            "vendor_id": "vendor-a",
            "amount": 1000,
        },
        "policy_pack": "finance_vendor_change_v1",
        "evidence_refs": ["ev-1"],
    }
    values.update(overrides)
    return ActionRequest(**values)


def test_canonical_json_is_stable_for_mapping_order():
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})
    assert parameters_hash({"b": 2, "a": 1}) == parameters_hash({"a": 1, "b": 2})


def test_policy_envelope_contains_explicit_security_context():
    envelope = action_envelope(request(), "action-1")
    assert envelope["protocol_version"] == "1.0"
    assert envelope["request_id"] == "req-canonical-1"
    assert envelope["agent"]["principal"] == "org:acme:finance"
    assert envelope["action"]["parameters"]["vendor_id"] == "vendor-a"
    assert envelope["policy"]["pack"] == "finance_vendor_change_v1"
    assert envelope["evidence_refs"] == ["ev-1"]
    assert "runtime" not in envelope


def test_each_security_relevant_mutation_changes_policy_hash():
    base = request()
    base_hash = action_hash(base, "action-1")
    mutations = [
        {"request_id": "req-canonical-2"},
        {"agent_id": "agent-2"},
        {"principal": "org:other:finance"},
        {"framework": "different"},
        {"action_type": "initiate_wire_transfer"},
        {"consequence_class": "financial_transfer"},
        {"purpose": "different purpose"},
        {"consumer": "erp:other-payables"},
        {"jurisdiction": "NG"},
        {"payload": {"vendor_id": "vendor-b", "amount": 1000}},
        {"payload": {"vendor_id": "vendor-a", "amount": 100000}},
        {"policy_pack": "generic"},
        {"evidence_refs": ["ev-2"]},
    ]
    assert all(action_hash(request(**mutation), "action-1") != base_hash for mutation in mutations)


def test_action_id_is_bound_to_the_hash():
    assert action_hash(request(), "action-1") != action_hash(request(), "action-2")
