"""Evidence Weave tests: stream binding, coverage and integrity, never grading."""
import copy
import pytest

from ncs_harness.evidence_weave import build_evidence_weave, verify_evidence_weave


def native(assessment_id="WEAVE-001"):
    return {
        "report_schema": "ncs-native-baseline-summary/0.1",
        "assessment_id": assessment_id,
        "probe_results": [
            {"probe_id":"NBB-001","probe_status":"repeatable-observations"},
            {"probe_id":"NBB-002","probe_status":"insufficient-repeats"},
        ],
        "grade_issued": False,
        "aggregate_score": None,
    }


def policy(assessment_id="WEAVE-001"):
    return {
        "report_schema": "ncs-policy-delta-summary/0.1",
        "assessment_id": assessment_id,
        "paired_results": [
            {"probe_id":"NBB-001","run_index":1,"assertion_changes":[
                {"classification":"improved-observed"},
                {"classification":"unresolved"},
            ]}
        ],
        "grade_issued": False,
        "aggregate_score": None,
    }


def application(assessment_id="WEAVE-001", status="partially-verified"):
    return {
        "assessment_id": assessment_id,
        "grade_eligible": False,
        "evidence_status": status,
        "observation": {
            "sink_invoked": True,
            "sink_state_before_sha256": "a"*64,
            "sink_state_after_sha256": "b"*64,
        },
    }


def test_all_streams_are_bound_and_no_grade_is_issued():
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=native(),
        policy_delta=policy(),
        application_records=[application()],
        declared_scope={"probe_pack":"NBB-0.1","scenario_pack":"Cyraduct-FG-0.1"},
    )
    assert weave["supplied_stream_count"] == 3
    assert weave["weave_status"] == "assembled-needs-review"
    assert weave["grade_compiler_input"] is False
    assert weave["grade_issued"] is False
    assert weave["grade_eligible"] is False
    assert verify_evidence_weave(weave)[0] is True


def test_missing_streams_are_explicit_and_weave_is_incomplete():
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=None,
        policy_delta=policy(),
        application_records=[],
    )
    assert weave["weave_status"] == "incomplete"
    assert "native-behavior-baseline" in weave["missing_streams"]
    assert "application-control-and-consequence" in weave["missing_streams"]


def test_assessment_id_mismatch_is_rejected():
    with pytest.raises(ValueError, match="assessment_id mismatch"):
        build_evidence_weave(
            assessment_id="WEAVE-001",
            native_baseline=native("OTHER"),
            policy_delta=policy(),
        )


def test_application_record_cannot_claim_grade_eligibility():
    item = application()
    item["grade_eligible"] = True
    with pytest.raises(ValueError, match="must not be marked grade eligible"):
        build_evidence_weave(
            assessment_id="WEAVE-001",
            native_baseline=native(),
            policy_delta=policy(),
            application_records=[item],
        )


def test_consequence_coverage_counts_only_explicit_observations():
    observed = application()
    unknown = application()
    unknown["observation"]["sink_invoked"] = None
    unknown["observation"]["sink_state_before_sha256"] = None
    unknown["observation"]["sink_state_after_sha256"] = None
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=native(),
        policy_delta=policy(),
        application_records=[observed, unknown],
    )
    app = next(x for x in weave["components"] if x["stream"] == "application-control-and-consequence")
    assert app["coverage"]["consequence_observed_count"] == 1
    assert app["coverage"]["record_count"] == 2


def test_failed_application_evidence_is_not_hidden():
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=native(),
        policy_delta=policy(),
        application_records=[application(status="failed")],
    )
    app = next(x for x in weave["components"] if x["stream"] == "application-control-and-consequence")
    assert app["coverage"]["failed_record_count"] == 1
    assert app["coverage"]["status"] == "observed-with-failures"


def test_tampering_with_weave_is_detected():
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=native(),
        policy_delta=policy(),
        application_records=[application()],
    )
    altered = copy.deepcopy(weave)
    altered["components"][0]["coverage"]["repeatable_probe_count"] = 999
    assert verify_evidence_weave(altered) == (False, "weave_digest_mismatch")


def test_native_repeatability_does_not_imply_grade():
    weave = build_evidence_weave(
        assessment_id="WEAVE-001",
        native_baseline=native(),
        policy_delta=policy(),
        application_records=[application(status="verified")],
    )
    assert weave["grade_compiler_input"] is False
    assert weave["grade_issued"] is False
    assert weave["grade_eligible"] is False
