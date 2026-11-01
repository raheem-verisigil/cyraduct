"""Tests for NCS Failure Evidence and Modification Rule Engine."""
import copy
import pytest
from ncs_harness.failure_evidence import build_failure_case, evaluate_modification_rule, normalize_observability_event, normalize_otel_event, verify_failure_case
D = "a" * 64
P = "b" * 64

def make_event(category="reliability", severity="high", status="confirmed", integrity="signed"):
    return normalize_observability_event(
        event_id="evt-001", observed_at="2026-11-01T10:00:00Z",
        source={"integration":"langfuse","event_type":"evaluation.failure","trace_id":"trace-1"},
        subject={"artifact_digest":D,"provider":"synthetic","model_name":"fixture-model"},
        failure={"category":category,"severity":severity,"signal_kind":"soft_failure","status":status,"confidence":0.9},
        evidence={"payload_digest":P,"evidence_refs":[]}, source_integrity=integrity,
        content_mode="none", assessment_id="NCS-TEST-001",
    )

def test_normalizes_provider_neutral_failure_signal_and_binds_artifact():
    result = make_event()
    assert result["schema"] == "ncs-failure-evidence/0.1"
    assert result["subject"]["artifact_digest"] == D
    assert result["grade_eligible"] is False

def test_rejects_missing_or_invalid_artifact_digest():
    with pytest.raises(ValueError, match="artifact_digest"):
        normalize_observability_event(
            event_id="x", observed_at="2026-11-01T10:00:00Z",
            source={"integration":"x","event_type":"x"}, subject={"artifact_digest":"model-name-only"},
            failure={"category":"reliability","severity":"low","signal_kind":"hard_error"},
            evidence={"payload_digest":P},
        )

def test_rejects_timezone_free_timestamp():
    with pytest.raises(ValueError, match="timezone"):
        normalize_observability_event(
            event_id="x", observed_at="2026-11-01T10:00:00",
            source={"integration":"x","event_type":"x"}, subject={"artifact_digest":D},
            failure={"category":"reliability","severity":"low","signal_kind":"hard_error"},
            evidence={"payload_digest":P},
        )

def test_rejects_invalid_confidence():
    with pytest.raises(ValueError, match="confidence"):
        normalize_observability_event(
            event_id="x", observed_at="2026-11-01T10:00:00Z",
            source={"integration":"x","event_type":"x"}, subject={"artifact_digest":D},
            failure={"category":"reliability","severity":"low","signal_kind":"hard_error","confidence":2},
            evidence={"payload_digest":P},
        )

def test_unverified_signal_never_triggers_confirmed_containment():
    decision = evaluate_modification_rule(make_event("safety","critical",integrity="unverified"))
    assert decision["decision_status"] == "recommendation-only"
    assert decision["containment"] == "consider-temporary-containment"
    assert decision["certificate_action"] == "NO_AUTOMATIC_CERTIFICATE_MUTATION"
    assert decision["execution_performed"] is False

def test_authenticated_confirmed_critical_safety_recommends_only():
    decision = evaluate_modification_rule(make_event("safety","critical"))
    assert decision["rule_id"] == "NCS-FMR-CONTAIN-001"
    assert decision["containment"] == "containment-recommended-not-executed"
    assert decision["execution_performed"] is False

def test_high_reliability_failure_routes_to_targeted_reassessment():
    decision = evaluate_modification_rule(make_event("reliability","high"))
    assert decision["rule_id"] == "NCS-FMR-REASSESS-001"
    assert decision["reassessment_scope"] == "targeted-reassessment"

def test_refuted_signal_does_not_trigger_reassessment():
    decision = evaluate_modification_rule(make_event(status="refuted"))
    assert decision["rule_id"] == "NCS-FMR-REFUTED-001"
    assert decision["reassessment_scope"].startswith("no-reassessment")

def test_otel_exception_mapping_is_conservative_and_content_free():
    result = normalize_otel_event({
        "id":"otel-1","name":"gen_ai.client.operation.exception",
        "observed_at":"2026-11-01T10:00:00Z","trace_id":"trace-1","span_id":"span-1",
        "attributes":{"error.type":"timeout","gen_ai.system":"provider-x","gen_ai.request.model":"model-y"},
    }, artifact_digest=D)
    assert result["failure"]["category"] == "reliability"
    assert result["failure"]["signal_kind"] == "hard_error"
    assert result["source_integrity"] == "unverified"
    assert result["evidence"]["content_mode"] == "none"
    assert "prompt" not in str(result).lower()

def test_failure_case_integrity_and_no_certificate_mutation():
    e = make_event("privacy","critical")
    case = build_failure_case(e,evaluate_modification_rule(e))
    assert verify_failure_case(case) == (True,"valid")
    assert case["certificate_status_change"] == "NONE"
    tampered = copy.deepcopy(case)
    tampered["case_status"] = "CLOSED"
    assert verify_failure_case(tampered) == (False,"case_digest_mismatch")

def test_rule_engine_rejects_cross_event_decision_binding():
    e = make_event()
    decision = evaluate_modification_rule(e)
    changed = copy.deepcopy(e)
    changed["event_id"] = "evt-other"
    with pytest.raises(ValueError, match="does not bind"):
        build_failure_case(changed,decision)
