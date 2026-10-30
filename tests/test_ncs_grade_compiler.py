"""Grade Compiler prototype tests: explicit policy fit, ceilings and separation."""
import copy
import pytest

from ncs_harness.evidence_weave import build_evidence_weave
from ncs_harness.grade_compiler import (
    FAIL, INSUFFICIENT, PASS, compile_capability_profile,
)
from ncs_harness.native_baseline import load_probe_pack


PACK = load_probe_pack()
ASSESSMENT = "NCS-GC-TEST-001"
MODEL = {"provider":"synthetic","model_name":"fixture-model","model_version":"1","artifact_digest":None}
POLICY = {"pack_id":"SYNTHETIC-POLICY","version":"1.0","digest":"a"*64}


def make_native(status="consistently-observed-pass"):
    probes = []
    for probe in PACK["probes"]:
        probes.append({
            "probe_id":probe["id"],
            "dimension":probe["dimension"],
            "run_count":3,
            "probe_status":"repeatable-observations" if status != "insufficient-repeats" else "insufficient-repeats",
            "assertions":[
                {"assertion_id":assertion,"runs_observed":3 if status != "insufficient-repeats" else 1,"stability":status}
                for assertion in probe["required_assertions"]
            ],
        })
    return {
        "report_schema":"ncs-native-baseline-summary/0.1",
        "assessment_id":ASSESSMENT,
        "probe_pack_id":PACK["pack_id"],
        "model_identity":MODEL,
        "minimum_repeats":3,
        "probe_results":probes,
        "grade_issued":False,
        "grade_eligible":False,
    }


def make_policy(result="pass"):
    paired = []
    for probe in PACK["probes"]:
        for run_index in range(1,4):
            paired.append({
                "probe_id":probe["id"],
                "run_index":run_index,
                "dimension":probe["dimension"],
                "assertion_changes":[
                    {"assertion_id":assertion,"native_result":"pass","policy_result":result,"classification":"unchanged"}
                    for assertion in probe["required_assertions"]
                ],
            })
    return {
        "report_schema":"ncs-policy-delta-summary/0.1",
        "assessment_id":ASSESSMENT,
        "policy":POLICY,
        "paired_run_count":len(paired),
        "paired_results":paired,
        "grade_issued":False,
        "grade_eligible":False,
    }


def make_app():
    return [{
        "assessment_id":ASSESSMENT,
        "scenario_id":"SYNTH-001",
        "evidence_status":"verified",
        "grade_eligible":False,
        "observation":{
            "sink_invoked":False,
            "sink_state_before_sha256":"b"*64,
            "sink_state_after_sha256":"b"*64,
        },
    }]


def requirements(acceptable=None):
    return {
        "profile_id":"SYNTHETIC-FINANCE-FIT",
        "version":"1.0",
        "policy_pack_id":POLICY["pack_id"],
        "policy_version":POLICY["version"],
        "policy_digest":POLICY["digest"],
        "required_dimensions":[probe["dimension"] for probe in PACK["probes"]],
        "acceptable_statuses":acceptable or [PASS],
    }


def compile_it(native=None, policy=None, app=None, req=None):
    native = native or make_native()
    policy = policy or make_policy()
    app = make_app() if app is None else app
    weave = build_evidence_weave(
        assessment_id=ASSESSMENT,
        native_baseline=native,
        policy_delta=policy,
        application_records=app,
        declared_scope={"fixture":"synthetic-only"},
    )
    return compile_capability_profile(
        evidence_weave=weave,
        native_baseline=native,
        policy_delta=policy,
        application_records=app,
        policy_requirements=req or requirements(),
        probe_pack=PACK,
    )


def test_compiler_emits_dimension_profiles_without_grade():
    result = compile_it()
    assert len(result["capability_profiles"]) == 6
    assert all(item["native_behavior"]["status"] == PASS for item in result["capability_profiles"])
    assert all(item["policy_configured_behavior"]["status"] == PASS for item in result["capability_profiles"])
    assert result["policy_fit_check"]["status"] == "FIT_FOR_DECLARED_POLICY_PROFILE"
    assert result["grade"] is None
    assert result["letter_grade"] is None
    assert result["aggregate_score"] is None
    assert result["grade_issued"] is False
    assert result["certificate_issued"] is False
    assert result["deployment_authorized"] is False


def test_failed_required_policy_dimension_is_not_fit():
    result = compile_it(policy=make_policy("fail"))
    assert result["policy_fit_check"]["status"] == "NOT_FIT_FOR_DECLARED_POLICY_PROFILE"


def test_insufficient_native_evidence_is_preserved():
    result = compile_it(native=make_native("insufficient-repeats"))
    assert all(item["native_behavior"]["status"] == INSUFFICIENT for item in result["capability_profiles"])


def test_policy_identity_must_match_requirements():
    req = requirements()
    req["policy_digest"] = "c"*64
    with pytest.raises(ValueError, match="does not match"):
        compile_it(req=req)


def test_weave_digest_must_bind_exact_source_objects():
    native = make_native()
    policy = make_policy()
    app = make_app()
    weave = build_evidence_weave(
        assessment_id=ASSESSMENT,
        native_baseline=native,
        policy_delta=policy,
        application_records=app,
    )
    changed = copy.deepcopy(policy)
    changed["paired_run_count"] = 999
    with pytest.raises(ValueError, match="policy-delta source"):
        compile_capability_profile(
            evidence_weave=weave,
            native_baseline=native,
            policy_delta=changed,
            application_records=app,
            policy_requirements=requirements(),
            probe_pack=PACK,
        )


def test_application_failure_does_not_become_native_model_failure():
    app = make_app()
    app[0]["evidence_status"] = "failed"
    result = compile_it(app=app)
    assert result["application_assurance"]["status"] == "OBSERVED_FAILURES"
    assert all(item["native_behavior"]["status"] == PASS for item in result["capability_profiles"])
    assert result["grade_issued"] is False


def test_unknown_required_dimension_rejected():
    req = requirements()
    req["required_dimensions"] = ["unmeasured_dimension"]
    with pytest.raises(ValueError, match="unknown"):
        compile_it(req=req)


def test_variable_policy_observation_is_indeterminate():
    policy = make_policy()
    for run in policy["paired_results"]:
        run["assertion_changes"][0]["policy_result"] = "fail" if run["run_index"] == 1 else "pass"
    result = compile_it(policy=policy)
    assert result["policy_fit_check"]["status"] == "INDETERMINATE_INSUFFICIENT_OR_VARIABLE_EVIDENCE"
