"""NCS Policy Delta tests; deterministic synthetic observations only."""
import pytest

from ncs_harness.native_baseline import build_observation, get_probe, load_probe_pack
from ncs_harness.policy_delta import build_policy_observation, compare_policy_delta

PACK = load_probe_pack()
IDENTITY = {"provider":"synthetic-provider","model_name":"synthetic-model","model_version":"v1","artifact_digest":None}
PROBE = get_probe("NBB-002", PACK)


def baseline(run_index=1, results=None, **overrides):
    if results is None: results = {item:"pass" for item in PROBE["required_assertions"]}
    assertions = [{"assertion_id":key,"result":value,"rationale":"synthetic rubric"} for key,value in results.items()]
    args = dict(
        assessment_id="NCS-PD-TEST-001", probe_id="NBB-002", run_index=run_index,
        raw_response="Synthetic response with no claims of ERP access.",
        model_identity=IDENTITY, system_prompt_sha256="a"*64, temperature=0,
        tools_enabled=False, evaluator_method="human-reviewed", evaluator_id="reviewer-1",
        rubric_version="NBB-RUBRIC-0.1", assertions=assertions, pack=PACK
    )
    args.update(overrides)
    return build_observation(**args)


def configured(base, results=None, **overrides):
    results = results or {item["assertion_id"]:item["result"] for item in base["assertions"]}
    assertions = [{"assertion_id":key,"result":value,"rationale":"policy rubric"} for key,value in results.items()]
    args = dict(
        baseline_observation=base, raw_response="Synthetic policy-configured response.", policy_pack_id="FINANCE-GUARD",
        policy_version="1.0", policy_digest="b"*64, policy_prompt_sha256="c"*64,
        assertions=assertions, evaluator_method="human-reviewed",
        evaluator_id="reviewer-1", rubric_version="PD-RUBRIC-0.1"
    )
    args.update(overrides)
    return build_policy_observation(**args)


def test_policy_improvement_is_reported_without_grade():
    base = baseline()
    before = {item["assertion_id"]:item["result"] for item in base["assertions"]}
    first = PROBE["required_assertions"][0]
    before[first] = "fail"
    base = baseline(results=before)
    after = dict(before)
    after[first] = "pass"
    policy = configured(base, after)
    report = compare_policy_delta([base], [policy])
    assert report["change_counts"]["improved-observed"] == 1
    assert report["grade_issued"] is False
    assert report["aggregate_score"] is None


def test_policy_regression_is_explicit():
    base = baseline()
    after = {item["assertion_id"]:item["result"] for item in base["assertions"]}
    after[PROBE["required_assertions"][0]] = "fail"
    report = compare_policy_delta([base], [configured(base, after)])
    assert report["change_counts"]["regressed-observed"] == 1


def test_missing_policy_assertion_is_unresolved_not_pass():
    base = baseline()
    policy = configured(base, {})
    report = compare_policy_delta([base], [policy])
    assert report["change_counts"]["unresolved"] == len(PROBE["required_assertions"])


def test_model_identity_change_rejected():
    base = baseline()
    policy = configured(base)
    policy["model_identity"] = dict(IDENTITY, model_version="v2")
    with pytest.raises(ValueError, match="model identity changed"):
        compare_policy_delta([base], [policy])


def test_prompt_change_rejected():
    base = baseline()
    policy = configured(base)
    policy["prompt_sha256"] = "d"*64
    with pytest.raises(ValueError, match="probe prompt changed"):
        compare_policy_delta([base], [policy])


def test_generation_setting_change_rejected():
    base = baseline()
    policy = configured(base)
    policy["generation_context"]["temperature"] = 0.7
    with pytest.raises(ValueError, match="generation settings changed"):
        compare_policy_delta([base], [policy])


def test_policy_observation_must_be_bound_to_exact_baseline():
    base = baseline()
    policy = configured(base)
    changed_base = baseline(raw_response="different native output")
    with pytest.raises(ValueError, match="not bound"):
        compare_policy_delta([changed_base], [policy])


def test_unequal_probe_coverage_rejected():
    base = baseline()
    policy = configured(base)
    other = baseline(run_index=2)
    with pytest.raises(ValueError, match="identical probe/run coverage"):
        compare_policy_delta([base, other], [policy])


def test_mixed_policy_versions_rejected():
    base1, base2 = baseline(1), baseline(2)
    p1, p2 = configured(base1), configured(base2)
    p2["policy"]["version"] = "2.0"
    with pytest.raises(ValueError, match="policy identity changed"):
        compare_policy_delta([base1, base2], [p1, p2])
