"""NCS certificate lifecycle and change-impact tests.

The v0.1 implementation must never issue a certificate.
"""
import copy
import pytest

from ncs_harness.certificate_lifecycle import (
    assess_change_impact,
    build_certificate_candidate,
    verify_change_impact,
)


def digest(char):
    return char * 64


def weave():
    return {
        "report_schema":"ncs-evidence-weave/0.1",
        "assessment_id":"NCS-CERT-TEST-001",
        "weave_status":"assembled-needs-review",
        "grade_issued":False,
        "components":[],
    }


def capability():
    return {
        "report_schema":"ncs-capability-profile-compiler/0.1",
        "assessment_id":"NCS-CERT-TEST-001",
        "model_identity":{
            "provider":"fixture",
            "model_name":"synthetic-model",
            "model_version":"1",
            "artifact_digest":digest("a"),
        },
        "grade_issued":False,
        "certificate_issued":False,
        "global_evidence_ceiling":"EXPERIMENTAL_NOT_GRADEABLE",
    }


def change(kind="model_weights"):
    return {
        "event_id":"CHANGE-001",
        "occurred_at":"2026-10-30T10:00:00Z",
        "change_type":kind,
        "old_digest":digest("a"),
        "new_digest":digest("b"),
        "source":"synthetic-test",
    }


def test_certificate_candidate_is_never_issued_even_with_valid_artifact():
    candidate = build_certificate_candidate(
        evidence_weave=weave(),
        capability_profile=capability(),
        build_record=None,
    )
    assert candidate["certificate_status"] == "NOT_ISSUED"
    assert candidate["certificate_id"] is None
    assert candidate["issuance_eligible"] is False
    assert candidate["signature"] is None
    assert candidate["transparency_log_entry"] is None
    assert "build_record_missing" in candidate["blockers"]
    assert any("not_implemented" in item for item in candidate["blockers"])


def test_candidate_requires_exact_artifact_digest():
    cap = capability()
    cap["model_identity"]["artifact_digest"] = None
    candidate = build_certificate_candidate(
        evidence_weave=weave(),
        capability_profile=cap,
        build_record=None,
    )
    assert "exact_model_artifact_digest_missing_or_unverified" in candidate["blockers"]


def test_material_model_change_invalidates_candidate_and_requires_full_reassessment():
    record = {"certificate_status":"NOT_ISSUED"}
    result = assess_change_impact(
        certificate_record=record,
        change_event=change("model_weights"),
    )
    assert result["reassessment_scope"] == "full-native-and-derived-reassessment"
    assert "native-behavior-baseline" in result["affected_evidence_streams"]
    assert result["certificate_action_recommendation"].startswith("NO_ACTIVE_CERTIFICATE")
    assert result["certificate_mutated"] is False
    assert verify_change_impact(result)[0] is True


def test_policy_pack_change_targets_policy_delta_and_fit_check():
    result = assess_change_impact(
        certificate_record={"certificate_status":"NOT_ISSUED"},
        change_event=change("policy_pack"),
    )
    assert result["affected_evidence_streams"] == ["policy-delta"]
    assert result["reassessment_scope"] == "policy-delta-and-fit-reassessment"


def test_issued_certificate_change_recommends_suspension_or_revocation_review():
    result = assess_change_impact(
        certificate_record={"certificate_status":"ISSUED"},
        change_event=change("model_version"),
    )
    assert result["certificate_action_recommendation"] == "SUSPEND_OR_REVOKE_PENDING_REASSESSMENT"
    assert result["automated_revocation_performed"] is False


def test_unknown_change_type_requires_manual_classification():
    with pytest.raises(ValueError, match="unknown change type"):
        assess_change_impact(
            certificate_record={"certificate_status":"NOT_ISSUED"},
            change_event=change("unknown_runtime_toggle"),
        )


def test_identical_digests_are_not_a_material_change():
    event = change("policy_pack")
    event["new_digest"] = event["old_digest"]
    with pytest.raises(ValueError, match="identical"):
        assess_change_impact(
            certificate_record={"certificate_status":"NOT_ISSUED"},
            change_event=event,
        )


def test_change_impact_tampering_is_detected():
    result = assess_change_impact(
        certificate_record={"certificate_status":"NOT_ISSUED"},
        change_event=change(),
    )
    altered = copy.deepcopy(result)
    altered["reassessment_scope"] = "no reassessment"
    assert verify_change_impact(altered) == (False, "impact_digest_mismatch")
