"""Tests for the NCS evidence collector; no network or application is used."""
import json

import pytest

from ncs_harness.collector import (
    append_hash_chained_record,
    build_evidence_record,
    verify_hash_chain,
)
from ncs_harness.report import build_report


COMMIT = "a" * 40


def sample_record(**overrides):
    args = {
        "assessment_id": "NCS-CYR-PILOT-001",
        "scenario_id": "NCS-CYR-FG-001",
        "repository": "https://github.com/raheem-verisigil/cyraduct",
        "commit_sha": COMMIT,
        "component": "attested.evaluate",
        "input_payload": {"vendor_id": "synthetic-001"},
        "application_decision": "allow",
        "expected_decision": "allow",
        "assertions": [{"assertion_id": "decision_matches", "result": "pass"}],
        "policy_pack": "finance_vendor_change_v1",
        "receipt_signature_valid": True,
        "sink_invoked": None,
    }
    args.update(overrides)
    return build_evidence_record(**args)


def test_collector_hashes_input_and_never_stores_raw_payload():
    record = sample_record()
    assert len(record["input"]["sha256"]) == 64
    assert record["input"]["redacted_excerpt"] is None
    assert "vendor_id" not in json.dumps(record)
    assert record["grade_eligible"] is False
    assert record["native_behavior_baseline"] == "not-assessed"


def test_unobserved_sink_is_unknown_not_false():
    record = sample_record(sink_invoked=None)
    assert record["observation"]["sink_invoked"] is None


def test_non_synthetic_data_is_rejected():
    with pytest.raises(ValueError, match="synthetic_data"):
        sample_record(synthetic_data=False)


def test_bad_commit_sha_is_rejected():
    with pytest.raises(ValueError, match="commit_sha"):
        sample_record(commit_sha="main")


def test_failure_cannot_be_reported_as_verified():
    record = sample_record(assertions=[
        {"assertion_id": "signature", "result": "fail"}
    ])
    assert record["evidence_status"] == "failed"


def test_hash_chained_ledger_detects_tampering(tmp_path):
    ledger = tmp_path / "evidence.jsonl"
    first = append_hash_chained_record(ledger, sample_record())
    second = append_hash_chained_record(
        ledger,
        sample_record(scenario_id="NCS-CYR-FG-002"),
    )
    assert second["previous_record_hash"] == first["record_hash"]
    assert verify_hash_chain(ledger)[0] is True

    lines = ledger.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["record"]["scenario_id"] = "changed-after-signoff"
    lines[0] = json.dumps(tampered)
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
    valid, reason = verify_hash_chain(ledger)
    assert valid is False
    assert reason == "record_hash_mismatch_at_line_1"



def test_decision_mismatch_is_failed_even_if_caller_assertions_pass():
    record = sample_record(
        application_decision="deny",
        expected_decision="allow",
        assertions=[{"assertion_id": "caller_assertion", "result": "pass"}],
    )
    assert record["evidence_status"] == "failed"
    decision_assertion = next(
        item for item in record["observation"]["assertions"]
        if item["assertion_id"] == "ncs_expected_decision_match"
    )
    assert decision_assertion["result"] == "fail"


def test_unobserved_decision_cannot_be_marked_verified():
    record = sample_record(
        application_decision=None,
        expected_decision="allow",
        assertions=[{"assertion_id": "caller_assertion", "result": "pass"}],
    )
    assert record["evidence_status"] == "partially-verified"



def test_policy_pass_with_unobserved_sink_is_only_partially_verified():
    record = sample_record(
        sink_invoked=None,
        receipt_id="synthetic-receipt-001",
        receipt_signature_valid=None,
        receipt_action_binding_valid=None,
    )
    assert record["evidence_status"] == "partially-verified"


def test_collector_refuses_to_append_to_tampered_ledger(tmp_path):
    ledger = tmp_path / "evidence.jsonl"
    append_hash_chained_record(ledger, sample_record())
    ledger.write_text('{"record_hash":"forged"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid evidence ledger"):
        append_hash_chained_record(ledger, sample_record())



def test_summary_report_verifies_chain_and_never_issues_grade(tmp_path):
    ledger = tmp_path / "evidence.jsonl"
    append_hash_chained_record(ledger, sample_record())
    report = build_report(ledger)
    assert report["ledger_integrity"] == "valid"
    assert report["record_count"] == 1
    assert report["grade_issued"] is False
    assert report["native_behavior_baseline"] == "not-assessed"


def test_summary_report_refuses_tampered_ledger(tmp_path):
    ledger = tmp_path / "evidence.jsonl"
    append_hash_chained_record(ledger, sample_record())
    ledger.write_text('{"record_hash":"forged"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="ledger verification failed"):
        build_report(ledger)
